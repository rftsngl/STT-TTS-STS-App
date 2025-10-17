from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

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

from .config import get_settings

MODEL_NAME = "medium"

_MODEL: Optional[WhisperModel] = None
_DEVICE: Optional[str] = None
_DEVICE_METADATA: Dict[str, Optional[str]] = {
    "configured": "auto",
    "effective": "cpu",
    "fallback_reason": None,
}


def _update_metadata(configured: str, effective: str, reason: Optional[str]) -> None:
    _DEVICE_METADATA["configured"] = configured
    _DEVICE_METADATA["effective"] = effective
    _DEVICE_METADATA["fallback_reason"] = reason


def get_device_metadata() -> Dict[str, Optional[str]]:
    return _DEVICE_METADATA.copy()


def _torch_cuda_ready() -> tuple[bool, Optional[str]]:
    if torch is None:
        return False, "torch_missing"
    try:
        if not torch.cuda.is_available():
            return False, "torch_cuda_unavailable"
        cudnn = getattr(getattr(torch, "backends", None), "cudnn", None)
        if cudnn is None or not cudnn.is_available():
            return False, "cuda_cudnn_missing"
        return True, None
    except Exception as exc:  # pragma: no cover
        logger.debug("Torch CUDA probe failed: {}", exc)
        return False, "torch_cuda_error"


def _probe_cuda() -> tuple[bool, Optional[str]]:
    # Prefer CTranslate2 detection if available and functional.
    if ctranslate2 is not None:
        try:
            count = ctranslate2.get_cuda_device_count()
            if count > 0:
                ready, reason = _torch_cuda_ready()
                if ready:
                    return True, None
                return False, reason or "cuda_backends_unavailable"
        except Exception as exc:  # pragma: no cover
            logger.debug("CTranslate2 CUDA probe failed: {}", exc)
            return False, "ctranslate2_cuda_error"
    return _torch_cuda_ready()


def _determine_device(explicit: str | None) -> str:
    configured = (explicit or "auto").lower()
    if configured == "cpu":
        device = "cpu"
        reason = None
    else:
        cuda_ready, probe_reason = _probe_cuda()
        if cuda_ready:
            device = "cuda"
            reason = None
        else:
            device = "cpu"
            if configured == "cuda":
                reason = probe_reason or "cuda_not_available"
            else:
                reason = probe_reason or "auto_cpu_fallback"
    _update_metadata(configured, device, reason)
    return device


def _compute_type(device: str) -> str:
    return "float16" if device == "cuda" else "int8"


def get_realtime_model() -> Tuple[WhisperModel, str]:
    global _MODEL, _DEVICE
    settings = get_settings()
    configured = settings.device or "auto"
    device = _determine_device(configured)
    if WhisperModel is None:
        raise RuntimeError("faster-whisper is not installed")

    if _MODEL is not None and _DEVICE == device:
        return _MODEL, device

    logger.info("Loading streaming model %s on %s", MODEL_NAME, device)
    try:
        _MODEL = WhisperModel(
            MODEL_NAME,
            device=device,
            compute_type=_compute_type(device),
        )
        _DEVICE = device
        return _MODEL, device
    except Exception as exc:
        if device == "cuda":
            reason = f"cuda_init_failed:{exc.__class__.__name__}"
            logger.warning("CUDA initialisation failed; falling back to CPU: {}", exc)
            _update_metadata(configured, "cpu", reason)
            _MODEL = WhisperModel(
                MODEL_NAME,
                device="cpu",
                compute_type=_compute_type("cpu"),
            )
            _DEVICE = "cpu"
            return _MODEL, "cpu"
        raise


def transcribe_realtime(
    audio: np.ndarray,
    language: str,
    initial_prompt: Optional[str] = None,
) -> Tuple[List, dict]:
    if audio.size == 0:
        return [], {}

    model, _ = get_realtime_model()
    segments, info = model.transcribe(
        audio=audio,
        language=language,
        vad_filter=True,
        beam_size=5,
        initial_prompt=initial_prompt,
    )
    return list(segments), info


def get_device_label(preload: bool = False) -> str:
    settings = get_settings()
    if preload:
        get_realtime_model()
    meta = get_device_metadata()
    device = meta.get("effective") or _determine_device(settings.device)
    return device
