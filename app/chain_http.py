from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.audio_utils import AudioTranscodeError, convert_to_wav, load_wav_int16
from app.config import get_settings
from app.metrics import Span, log_metrics
from app.noise import reduce_noise_offline
from app.resilience.watchdog import wrap_stream
from app.voice_utils import get_eleven_provider, media_type_for_format, resolve_voice_id
from providers.elevenlabs_tts import ElevenLabsError
from app.textnorm import summarize_term_changes
from app.stt import MODEL_NAME, _determine_device, _get_model, _prepare_segments
from app.models_rt import get_device_metadata
from app.security.api_key import require_api_key

router = APIRouter()


def _convert_to_wav(source_path: Path) -> tuple[Path, float]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        target = Path(tmp.name)

    try:
        duration = convert_to_wav(source_path, target, sample_rate=16000, channels=1)
    except AudioTranscodeError as exc:
        if str(exc) == "FORMAT_UNSUPPORTED":
            raise HTTPException(
                status_code=400,
                detail={"code": "FORMAT_UNSUPPORTED", "detail": "Ses dosyasi cozumlenemedi"},
            ) from None
        raise HTTPException(
            status_code=500,
            detail={"code": "DECODE_FAILED", "detail": "Ses dosyasi cozumlenemedi"},
        ) from exc

    return target, duration

def _save_transcript(text: str) -> Path:
    transcripts_dir = Path("data/transcripts")
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = transcripts_dir / f"{timestamp}.txt"
    path.write_text(text, encoding="utf-8")
    return path


@router.post("/speak")
async def speak_http(
    audio_file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    voice_id: Optional[str] = Form(None),
    voice_alias: Optional[str] = Form(None),
    model_id: Optional[str] = Form(None),
    output_format: Optional[str] = Form(None),
    save_transcript: Optional[int] = Form(0),
) -> StreamingResponse:
    settings = get_settings()
    language = language or settings.default_language

    provider = get_eleven_provider(require=True)
    resolved_voice_id = resolve_voice_id(voice_id, voice_alias, settings)
    fmt = output_format or settings.eleven_output_format

    original_suffix = Path(audio_file.filename or "").suffix or ".bin"
    temp_source = tempfile.NamedTemporaryFile(delete=False, suffix=original_suffix)
    try:
        with temp_source:
            while chunk := await audio_file.read(1024 * 1024):
                temp_source.write(chunk)

        metrics = {"route": "speak_http", "language": language, "model": MODEL_NAME}
        span_total = Span()
        span_decode = Span()
        wav_path, duration = _convert_to_wav(Path(temp_source.name))
        decode_ms = span_decode.duration_ms
        if duration > settings.max_duration_seconds:
            raise HTTPException(
                status_code=413,
                detail={"code": "AUDIO_TOO_LONG", "limit_sec": settings.max_duration_seconds},
            )

        device_choice = _determine_device(settings.device)
        try:
            model = _get_model(device_choice)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail={"code": "STT_UNAVAILABLE", "detail": str(exc)},
            ) from exc
        meta = get_device_metadata()
        effective_device = meta.get("effective", device_choice)
        metrics["device_fallback_reason"] = meta.get("fallback_reason")

        noise_ms = 0.0
        if settings.noise_suppressor != "off":
            noise_span = Span()
            try:
                samples, sample_rate = load_wav_int16(wav_path)
                if sample_rate != 16000:
                    samples = samples.astype(np.int16)
                reduced = reduce_noise_offline(samples, 16000, settings)
                if reduced is not None and reduced.size == samples.size:
                    sf.write(str(wav_path), reduced.astype(np.int16), 16000, subtype="PCM_16")
            except Exception as exc:
                logger.debug("Noise suppression skipped: {}", exc)
            noise_ms = noise_span.duration_ms

        span_stt = Span()
        segments_iter, _ = model.transcribe(
            str(wav_path),
            language=language,
            vad_filter=True,
            beam_size=5,
            word_timestamps=False,
        )
        stt_ms = span_stt.duration_ms
        span_norm = Span()
        _, final_text, term_changes = _prepare_segments(segments_iter, include_words=False)
        norm_ms = span_norm.duration_ms
        terms_summary = summarize_term_changes(term_changes)

        if not final_text or len(final_text) < settings.min_chars:
            raise HTTPException(
                status_code=422,
                detail={"code": "EMPTY_TRANSCRIPT", "detail": "Metin cikarimi yetersiz cikti"},
            )

        if save_transcript:
            _save_transcript(final_text)

        try:
            stream_iterator = provider.stream_tts(
                text=final_text,
                voice_id=resolved_voice_id,
                language=language,
                model_id=model_id,
                output_format=fmt,
            )
        except ElevenLabsError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "detail": exc.detail},
            ) from exc

        span_tts = Span()
        queue_span = Span()
        queue_captured = False

        def generator():
            nonlocal queue_captured
            try:
                for chunk in stream_iterator:
                    if not queue_captured:
                        metrics["tts_queue_ms"] = round(queue_span.duration_ms, 2)
                        queue_captured = True
                    yield chunk
            finally:
                metadata = getattr(provider, "last_stream_metadata", None)
                metrics["retries"] = 0
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
                        "tts_queue_ms": round(metrics.get("tts_queue_ms", 0.0), 2),
                        "tts_stream_ms": round(span_tts.duration_ms, 2),
                        "total_ms": round(span_total.duration_ms, 2),
                    }
                )
                if isinstance(metadata, dict):
                    if metadata.get("cb_state"):
                        metrics["cb_state"] = metadata.get("cb_state")
                    metrics["retries"] = metadata.get("retries", 0)
                log_metrics(metrics)
    finally:
        try:
            os.remove(temp_source.name)
        except OSError:
            pass
        try:
            if "wav_path" in locals():
                os.remove(wav_path)
        except OSError:
            pass

    wrapped = wrap_stream(generator(), settings.http_write_timeout_sec)
    return StreamingResponse(wrapped, media_type=media_type_for_format(fmt))


@router.post("/speak/microphone")
async def speak_microphone(
    request: Request,
    language: Optional[str] = Form(None),  # noqa: F841
    voice_id: Optional[str] = Form(None),  # noqa: F841
    voice_alias: Optional[str] = Form(None),  # noqa: F841
    model_id: Optional[str] = Form(None),  # noqa: F841
    output_format: Optional[str] = Form(None),  # noqa: F841
    save_transcript: Optional[int] = Form(0),  # noqa: F841
) -> StreamingResponse:
    """Mikrofon ile ses kaydı yapıp STT+TTS işlemi gerçekleştirir."""
    response = await require_api_key(request)
    if response is not None:
        return response
    
    # Mikrofon API'si frontend'de implement edilmiştir
    # Frontend mikrofon kaydı yapıp dosya olarak /speak endpoint'ine gönderiyor
    # Bu endpoint sadece yönlendirme amaçlıdır
    
    raise HTTPException(
        status_code=400,
        detail={"code": "MICROPHONE_NOT_SUPPORTED", "detail": "Mikrofon API'si frontend'de implement edilmiştir. Lütfen /speak endpoint'ini kullanın."}
    )
