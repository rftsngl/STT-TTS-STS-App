from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field

from app.voice_utils import get_eleven_provider
from providers.elevenlabs_tts import (
    ElevenLabsError,
    delete_alias,
    list_aliases,
    save_alias,
)

router = APIRouter()


class AliasRequest(BaseModel):
    alias: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1)
    name: Optional[str] = None


@router.get("/providers/elevenlabs/voices")
async def list_provider_voices(request: Request):
    # Get ElevenLabs API key from header or settings
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    provider = get_eleven_provider(require=False, api_key=elevenlabs_key)
    if provider is None:
        raise HTTPException(
            status_code=501,
            detail={"code": "TTS_NOT_CONFIGURED", "detail": "ElevenLabs API anahtarı tanımlı değil. Lütfen admin panelinden API anahtarınızı girin."},
        )
    try:
        voices = provider.list_voices()
    except ElevenLabsError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "detail": exc.detail},
        ) from exc
    return {"voices": voices}


@router.get("/voices")
async def list_all_voices(request: Request):
    combined: List[Dict[str, object]] = []
    # Get ElevenLabs API key from header or settings
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    provider = get_eleven_provider(require=False, api_key=elevenlabs_key)
    if provider:
        try:
            for voice in provider.list_voices():
                entry = dict(voice)
                entry["source"] = "builtin"
                combined.append(entry)
        except ElevenLabsError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "detail": exc.detail},
            ) from exc
    for alias in list_aliases():
        entry = dict(alias)
        entry["source"] = "alias"
        combined.append(entry)
    return {"voices": combined}


@router.get("/voices/aliases")
async def get_aliases():
    return {"aliases": list_aliases()}


@router.post("/voices/aliases")
async def create_or_update_alias(payload: AliasRequest):
    entry = save_alias(
        alias=payload.alias,
        voice_id=payload.voice_id,
        name=payload.name or payload.alias,
        source="builtin",
    )
    return entry


@router.delete("/voices/aliases/{alias}")
async def remove_alias(alias: str = Path(..., min_length=1)):
    try:
        delete_alias(alias)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ALIAS_NOT_FOUND", "detail": f"Alias bulunamadı: {alias}"},
        ) from None
    return {"alias": alias, "deleted": True}
