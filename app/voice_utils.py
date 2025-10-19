from __future__ import annotations

import threading
from typing import Dict, Optional

from fastapi import HTTPException
from loguru import logger

from app.config import Settings, get_settings
from app.database import get_database, DatabaseError, EncryptionError
from providers.elevenlabs_tts import ElevenLabsProvider, resolve_alias


# Provider cache: {api_key_hash: provider_instance}
_provider_cache: Dict[str, ElevenLabsProvider] = {}
_cache_lock = threading.Lock()


def _get_api_key_from_database() -> Optional[str]:
    """Get ElevenLabs API key from database."""
    try:
        db = get_database()
        return db.get_api_key("elevenlabs")
    except (DatabaseError, EncryptionError) as e:
        logger.debug("Could not retrieve API key from database: %s", str(e))
        return None


def clear_provider_cache() -> None:
    """Clear the provider cache. Call this when API keys change."""
    global _provider_cache
    with _cache_lock:
        _provider_cache.clear()
        logger.debug("Provider cache cleared")


def get_eleven_provider(require: bool = True, api_key: Optional[str] = None) -> Optional[ElevenLabsProvider]:
    settings = get_settings()

    # Use provided API key or get from database (NO .env fallback)
    if api_key:
        raw_key = api_key.strip()
    else:
        # Get from database only - no fallback to .env file
        raw_key = _get_api_key_from_database()

    is_placeholder = raw_key and (raw_key.lower().startswith('your-') or raw_key.lower().startswith('demo-'))
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

    # Check cache first (Issue 3: Avoid redundant provider initialization)
    cache_key = raw_key[:20]  # Use first 20 chars as cache key

    with _cache_lock:
        if cache_key in _provider_cache:
            logger.debug("Returning cached ElevenLabs provider")
            return _provider_cache[cache_key]

        # Create new provider instance
        provider = ElevenLabsProvider(
            api_key=raw_key,
            model_id=settings.eleven_model_id,
            output_format=settings.eleven_output_format,
        )

        # Cache it
        _provider_cache[cache_key] = provider
        logger.debug("Created and cached new ElevenLabs provider")

        return provider


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
