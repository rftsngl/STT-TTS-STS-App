import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, Form, UploadFile, Request
from fastapi.responses import JSONResponse
from loguru import logger

from .audio_utils import AudioTranscodeError, convert_to_wav, load_wav_int16
from .config import get_settings
from .metrics import Span, log_metrics
from .noise import reduce_noise_offline
from .textnorm import apply_terms, normalize_text, summarize_term_changes
from .models_rt import get_device_metadata
from .security.api_key import require_api_key

try:  # pragma: no cover - optional dependency
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    import ctranslate2  # type: ignore
except Exception:  # pragma: no cover
    ctranslate2 = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover
    WhisperModel = None  # type: ignore[assignment]

router = APIRouter()

MODEL_NAME = "medium"
TMP_DIR = Path(tempfile.gettempdir())

_model: Optional[WhisperModel] = None
_model_device: Optional[str] = None


def _cuda_available() -> bool:
    if ctranslate2 is not None:
        try:
            if ctranslate2.get_cuda_device_count() > 0:
                return True
        except Exception as exc:  # pragma: no cover
            logger.debug("Failed to query CTranslate2 CUDA devices: {}", exc)
    if torch is not None:
        try:
            if torch.cuda.is_available():
                return True
        except Exception as exc:  # pragma: no cover
            logger.debug("Torch CUDA availability check failed: {}", exc)
    return False


def _determine_device(explicit: str | None = None) -> str:
    if explicit == "cuda":
        if _cuda_available():
            return "cuda"
        raise RuntimeError("CUDA requested but no compatible GPU was detected")
    if explicit == "cpu":
        return "cpu"
    return "cuda" if _cuda_available() else "cpu"


def _compute_type(device: str) -> str:
    return "float16" if device == "cuda" else "int8"


def _get_model(device: str) -> WhisperModel:
    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not installed")
    global _model, _model_device
    if _model is not None and _model_device == device:
        return _model
    logger.info("Loading faster-whisper model %s on %s", MODEL_NAME, device)
    _model = WhisperModel(
        MODEL_NAME,
        device=device,
        compute_type=_compute_type(device),
    )
    _model_device = device
    return _model


def _build_temp_path(suffix: str) -> Path:
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=TMP_DIR)
    path = Path(handle.name)
    handle.close()
    return path


def _json_error(status_code: int, payload: Dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)


def _transform_audio(source: Path) -> tuple[Path, float]:
    target_path = _build_temp_path(".wav")
    try:
        duration_sec = convert_to_wav(source, target_path, sample_rate=16000, channels=1)
    except AudioTranscodeError as exc:
        if str(exc) == "FORMAT_UNSUPPORTED":
            raise ValueError("FORMAT_UNSUPPORTED") from None
        logger.exception("Audio transcode error: {}", exc)
        raise RuntimeError("DECODE_FAILED") from exc
    return target_path, duration_sec


def _prepare_segments(
    whisper_segments: Any,
    include_words: bool,
) -> tuple[List[Dict[str, Any]], str, List[Dict[str, Any]]]:
    segments: List[Dict[str, Any]] = []
    segment_texts: List[str] = []
    changes: List[Dict[str, Any]] = []

    for segment in whisper_segments:
        raw_text = normalize_text(segment.text or "")
        if not raw_text:
            continue
        text_with_terms, segment_changes = apply_terms(raw_text)
        if segment_changes:
            changes.extend(segment_changes)
        segment_texts.append(text_with_terms)
        segment_entry: Dict[str, Any] = {
            "id": segment.id,
            "start_sec": round(float(segment.start or 0.0), 3),
            "end_sec": round(float(segment.end or 0.0), 3),
            "text": text_with_terms,
        }
        if include_words and getattr(segment, "words", None):
            words: List[Dict[str, Any]] = []
            for word in segment.words:
                words.append(
                    {
                        "text": word.word,
                        "start_sec": round(float(word.start or 0.0), 3),
                        "end_sec": round(float(word.end or 0.0), 3),
                        "probability": getattr(word, "probability", None),
                    }
                )
            segment_entry["words"] = words
        segments.append(segment_entry)
    combined = " ".join(segment_texts).strip()
    final_text = normalize_text(combined) if combined else ""
    return segments, final_text, changes


@router.post("/stt")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    timestamps: Optional[str] = Form(None),
) -> JSONResponse:
    if WhisperModel is None:
        return _json_error(
            503,
            {"code": "STT_UNAVAILABLE", "message": "faster-whisper paketini kurmadan STT kullanılamaz"},
        )
    settings = get_settings()
    language = language or settings.default_language
    timestamps = timestamps or settings.default_timestamps

    if timestamps not in {"segments", "words"}:
        return _json_error(400, {"code": "INVALID_PARAMETER", "message": "timestamps must be 'segments' or 'words'"})

    original_suffix = Path(audio_file.filename or "").suffix or ".bin"
    original_path = _build_temp_path(original_suffix)
    converted_path: Optional[Path] = None

    try:
        metrics = {
            "route": "stt",
            "language": language,
            "alias": None,
        }
        span_total = Span()
        with original_path.open("wb") as buffer:
            while chunk := await audio_file.read(1024 * 1024):
                buffer.write(chunk)

        span_decode = Span()
        converted_path, duration_sec = _transform_audio(original_path)
        decode_ms = span_decode.duration_ms
        if duration_sec > settings.max_duration_seconds:
            return _json_error(413, {"code": "AUDIO_TOO_LONG", "limit_sec": settings.max_duration_seconds})

        include_words = timestamps == "words"
        device_choice = _determine_device(settings.device)
        try:
            model = _get_model(device_choice)
        except RuntimeError as exc:
            return _json_error(503, {"code": "STT_UNAVAILABLE", "message": str(exc)})
        meta = get_device_metadata()
        effective_device = meta.get("effective", device_choice)
        metrics["device_fallback_reason"] = meta.get("fallback_reason")

        noise_ms = 0.0
        if settings.noise_suppressor != "off":
            noise_span = Span()
            try:
                samples, sample_rate = load_wav_int16(converted_path)
                if sample_rate != 16000:
                    samples = samples.astype(np.int16)
                reduced = reduce_noise_offline(samples, 16000, settings)
                if reduced is not None and reduced.size == samples.size:
                    sf.write(str(converted_path), reduced.astype(np.int16), 16000, subtype="PCM_16")
            except Exception as exc:
                logger.debug("Noise suppression skipped: {}", exc)
            noise_ms = noise_span.duration_ms

        span_stt = Span()
        segments_iter, _ = model.transcribe(
            str(converted_path),
            language=language,
            vad_filter=True,
            beam_size=5,
            word_timestamps=include_words,
        )
        stt_ms = span_stt.duration_ms
        span_norm = Span()
        segments, final_text, term_changes = _prepare_segments(segments_iter, include_words)
        norm_ms = span_norm.duration_ms
        response: Dict[str, Any] = {"text": final_text, "segments": segments}
        terms_summary = summarize_term_changes(term_changes)
        metrics.update(
            {
                "device": effective_device or device_choice,
                "compute_type": getattr(model, "compute_type", None),
                "model": MODEL_NAME,
                "decode_ms": round(decode_ms, 2),
                "noise_ms": round(noise_ms, 2),
                "vad_ms": 0.0,
                "stt_ms": round(stt_ms, 2),
                "norm_ms": round(norm_ms, 2),
                "terms_changes": terms_summary["count"],
                "terms_preview": terms_summary["items"],
                "tts_queue_ms": 0.0,
                "tts_stream_ms": 0.0,
                "total_ms": round(span_total.duration_ms, 2),
            }
        )
        log_metrics(metrics)
        return JSONResponse(status_code=200, content=response)
    except ValueError as exc:
        if str(exc) == "FORMAT_UNSUPPORTED":
            return _json_error(400, {"code": "FORMAT_UNSUPPORTED"})
        logger.exception("Value error during transcription: %s", exc)
        return _json_error(400, {"code": "INVALID_REQUEST"})
    except RuntimeError as exc:
        logger.exception("Runtime error during transcription: %s", exc)
        return _json_error(500, {"code": "INTERNAL_ERROR"})
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error during transcription: %s", exc)
        return _json_error(500, {"code": "INTERNAL_ERROR"})
    finally:
        try:
            os.remove(original_path)
        except OSError:
            pass
        if converted_path:
            try:
                os.remove(converted_path)
            except OSError:
                pass


@router.post("/stt/microphone")
async def transcribe_microphone(
    request: Request,
    language: Optional[str] = Form(None),  # noqa: F841
    timestamps: Optional[str] = Form(None),  # noqa: F841
) -> JSONResponse:
    """Mikrofon ile ses kaydı yapıp STT işlemi gerçekleştirir."""
    response = await require_api_key(request)
    if response is not None:
        return response
    
    # Mikrofon STT API'si frontend'de implement edilmiştir
    # Frontend mikrofon kaydı yapıp dosya olarak /stt endpoint'ine gönderiyor
    # Bu endpoint sadece yönlendirme amaçlıdır
    
    return _json_error(
        400,
        {"code": "MICROPHONE_NOT_SUPPORTED", "message": "Mikrofon STT API'si frontend'de implement edilmiştir. Lütfen /stt endpoint'ini kullanın."}
    )
