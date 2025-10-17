from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.metrics import Span, log_metrics
from app.resilience.watchdog import wrap_stream
from app.voice_utils import get_eleven_provider, media_type_for_format, resolve_voice_id
from providers.elevenlabs_tts import ElevenLabsError

router = APIRouter()


class TTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    voice_alias: Optional[str] = None
    voice_id: Optional[str] = None
    speaker_wav: Optional[str] = None  # unsupported for ElevenLabs
    model_id: Optional[str] = None
    output_format: Optional[str] = None
    language: Optional[str] = None
    stability: Optional[float] = None
    similarity_boost: Optional[float] = None
    style: Optional[float] = None
    use_speaker_boost: Optional[bool] = None
    optimize_streaming_latency: Optional[int] = None
    use_voice_consistency: Optional[bool] = None


@router.post("/tts")
async def cloud_tts(payload: TTSRequest, request: Request) -> StreamingResponse:
    settings = get_settings()

    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_TEXT", "detail": "Metin alanı boş olamaz"},
        )
    if payload.speaker_wav:
        raise HTTPException(
            status_code=422,
            detail={"code": "SPEAKER_WAV_UNSUPPORTED", "detail": "speaker_wav sadece ElevenLabs IVC ile kullanılabilir"},
        )

    # Get ElevenLabs API key from header or settings
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    
    voice_id = resolve_voice_id(payload.voice_id, payload.voice_alias, settings)
    provider = get_eleven_provider(require=True, api_key=elevenlabs_key)
    fmt = payload.output_format or settings.eleven_output_format
    language = payload.language or settings.eleven_tts_language

    voice_settings: Dict[str, object] = {}
    if payload.stability is not None:
        voice_settings["stability"] = payload.stability
    if payload.similarity_boost is not None:
        voice_settings["similarity_boost"] = payload.similarity_boost
    if payload.style is not None:
        voice_settings["style"] = payload.style
    if payload.use_speaker_boost is not None:
        voice_settings["use_speaker_boost"] = payload.use_speaker_boost
    if payload.optimize_streaming_latency is not None:
        voice_settings["optimize_streaming_latency"] = payload.optimize_streaming_latency
    if payload.use_voice_consistency is not None:
        voice_settings["use_voice_consistency"] = payload.use_voice_consistency

    try:
        stream = provider.stream_tts(
            text=payload.text.strip(),
            voice_id=voice_id,
            voice_settings=voice_settings or None,
            language=language,
            model_id=payload.model_id,
            output_format=fmt,
        )
    except ElevenLabsError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "detail": exc.detail},
        ) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail={"code": "TTS_FAILED", "detail": "ElevenLabs TTS çağrısı başarısız oldu"},
        ) from exc

    stream_span = Span()

    def generator():
        try:
            for chunk in stream:
                yield chunk
        finally:
            metadata = getattr(provider, "last_stream_metadata", None)
            entry = {
                "route": "tts_cloud",
                "tts_stream_ms": round(stream_span.duration_ms, 2),
                "retries": 0,
            }
            if isinstance(metadata, dict):
                if metadata.get("cb_state"):
                    entry["cb_state"] = metadata.get("cb_state")
                entry["retries"] = metadata.get("retries", 0)
            log_metrics(entry)

    wrapped = wrap_stream(generator(), settings.http_write_timeout_sec)
    return StreamingResponse(wrapped, media_type=media_type_for_format(fmt))
