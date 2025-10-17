from __future__ import annotations

import io
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger

from app.config import get_settings
from app.security.api_key import require_api_key
from app.voice_utils import get_eleven_provider

router = APIRouter()


@router.post("/audio/isolation")
async def isolate_audio(
    audio_file: UploadFile = File(...),
    isolation_type: str = Form("voice_enhancement"),
    noise_reduction: str = Form("high"),
    output_format: str = Form("wav"),
    request: Request = None
) -> StreamingResponse:
    """Ses dosyasını temizler ve ses kalitesini artırır."""
    _require_api_key(request)

    # Desteklenen formatları kontrol et
    supported_formats = ["wav", "mp3", "flac", "ogg", "m4a"]
    if output_format not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen output format. Desteklenen formatlar: {supported_formats}"
        )

    # Desteklenen isolation türlerini kontrol et
    supported_isolation_types = ["voice_enhancement", "noise_reduction", "vocal_isolation", "instrumental_isolation"]
    if isolation_type not in supported_isolation_types:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen isolation type. Desteklenen türler: {supported_isolation_types}"
        )

    # Desteklenen noise reduction seviyelerini kontrol et
    supported_noise_levels = ["low", "medium", "high", "off"]
    if noise_reduction not in supported_noise_levels:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen noise reduction seviyesi. Desteklenen seviyeler: {supported_noise_levels}"
        )

    # Dosya boyutunu kontrol et (max 50MB)
    max_file_size = 50 * 1024 * 1024  # 50MB
    if audio_file.size and audio_file.size > max_file_size:
        raise HTTPException(
            status_code=413,
            detail="Dosya boyutu çok büyük. Maksimum 50MB dosya yükleyebilirsiniz."
        )

    try:
        # Audio dosyasını oku
        audio_data = await audio_file.read()
        logger.info(f"Audio isolation başlatılıyor: {len(audio_data)} bytes, type: {isolation_type}")

        # Provider'ı al
        provider = get_eleven_provider()

        # Audio isolation işlemini başlat
        isolated_audio = await provider.isolate_audio(
            audio_data=audio_data,
            isolation_type=isolation_type,
            noise_reduction=noise_reduction,
            output_format=output_format
        )

        logger.info(f"Audio isolation tamamlandı: {len(isolated_audio)} bytes")

        # İşlenmiş dosyayı döndür
        filename = f"isolated_audio.{output_format}"

        return StreamingResponse(
            io.BytesIO(isolated_audio),
            media_type=f"audio/{output_format}",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(isolated_audio))
            }
        )

    except Exception as e:
        logger.error(f"Audio isolation hatası: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ses işleme hatası: {str(e)}"
        )
