from __future__ import annotations

import os
import tempfile
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.voice_utils import get_eleven_provider
from providers.elevenlabs_tts import ElevenLabsError, save_alias

router = APIRouter()


@router.post("/providers/elevenlabs/ivc")
async def create_elevenlabs_voice(
    name: str = Form(...),
    alias: str = Form(default="user"),
    description: str = Form(default=""),
    files: List[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(
            status_code=422,
            detail={"code": "NO_FILES", "detail": "En az bir ses dosyası yükleyin"},
        )

    provider = get_eleven_provider(require=True)
    temp_paths: List[str] = []

    try:
        for upload in files:
            suffix = os.path.splitext(upload.filename or "")[1] or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                data = await upload.read()
                tmp.write(data)
                temp_paths.append(tmp.name)

        voice_id = provider.create_ivc(name=name, files=temp_paths, description=description)
    except ElevenLabsError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "detail": exc.detail},
        ) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail={"code": "IVC_FAILED", "detail": "Voice cloning başarısız oldu"},
        ) from exc
    finally:
        for path in temp_paths:
            try:
                os.remove(path)
            except OSError:
                pass

    entry = save_alias(alias=alias or "user", voice_id=voice_id, name=name, source="ivc")
    return {"voice_id": voice_id, "alias": entry.get("alias")}
