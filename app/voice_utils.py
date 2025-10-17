from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from app.config import Settings, get_settings
from providers.elevenlabs_tts import ElevenLabsProvider, resolve_alias


def get_eleven_provider(require: bool = True, api_key: Optional[str] = None) -> Optional[ElevenLabsProvider]:
    settings = get_settings()
    
    # Use provided API key or fall back to settings
    if api_key:
        raw_key = api_key.strip()
    else:
        raw_key = (settings.xi_api_key or '').strip()
    
    is_placeholder = raw_key.lower().startswith('your-') or raw_key.lower().startswith('demo-')
    if not raw_key or is_placeholder or not raw_key.startswith('sk_'):
        if require:
            raise HTTPException(
                status_code=501,
                detail={
                    "code": "TTS_NOT_CONFIGURED",
                    "detail": "ElevenLabs API anahtarı tanımlı değil. Lütfen admin panelinden API anahtarınızı girin.",
                },
            )
        return None
    return ElevenLabsProvider(
        api_key=raw_key,
        model_id=settings.eleven_model_id,
        output_format=settings.eleven_output_format,
    )


def resolve_voice_id(
    voice_id: Optional[str],
    voice_alias: Optional[str],
    settings: Optional[Settings] = None,
) -> str:
    settings = settings or get_settings()

    if voice_id:
        return voice_id

    alias_sequence = []
    if voice_alias:
        alias_sequence.append(voice_alias)
    if settings.eleven_default_voice_alias:
        alias_sequence.append(settings.eleven_default_voice_alias)

    for alias in alias_sequence:
        if not alias:
            continue
        try:
            return resolve_alias(alias)
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail={"code": "ALIAS_NOT_FOUND", "detail": f"Alias bulunamadi: {alias}"},
            ) from None

    fallback = settings.eleven_default_voice_id
    if fallback:
        return fallback

    raise HTTPException(
        status_code=422,
        detail={"code": "VOICE_REQUIRED", "detail": "Bir voice_id veya voice_alias belirtin"},
    )


def media_type_for_format(output_format: str) -> str:
    fmt = (output_format or '').lower()
    if fmt.startswith('mp3'):
        return 'audio/mpeg'
    if fmt.startswith('wav'):
        return 'audio/wav'
    return 'application/octet-stream'
