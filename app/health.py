from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter
from loguru import logger

from app.config import get_settings
from app.terms_store import get_terms_store
from app.models_rt import get_device_metadata
from app.voice_utils import get_eleven_provider

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None  # type: ignore[assignment]

try:
    import ctranslate2
except ImportError:  # pragma: no cover
    ctranslate2 = None  # type: ignore[assignment]


router = APIRouter()


@lru_cache(maxsize=1)
def _ffmpeg_executable() -> Path | None:
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return None
    base = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
    if not base.exists():
        return None
    for candidate in sorted(base.rglob("ffmpeg.exe"), reverse=True):
        if "ffmpeg" in candidate.name.lower():
            return candidate
    return None


def _ffmpeg_version_line() -> str:
    executable = _ffmpeg_executable()
    if not executable:
        return "not found"
    try:
        result = subprocess.run(
            [str(executable), "-version"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as exc:  # pragma: no cover
        logger.debug("ffmpeg invocation failed: {}", exc)
        return "not found"
    if result.stdout:
        return result.stdout.splitlines()[0]
    return "not found"


def _torch_cuda_available() -> bool:
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception as exc:  # pragma: no cover
        logger.debug("Torch CUDA availability check failed: {}", exc)
        return False


def _ctranslate2_cuda_count() -> int:
    if "ctranslate2" not in globals() or ctranslate2 is None:  # type: ignore[name-defined]
        return 0
    try:
        return int(ctranslate2.get_cuda_device_count())  # type: ignore[name-defined]
    except Exception as exc:  # pragma: no cover
        logger.debug("CTranslate2 CUDA device check failed: {}", exc)
        return 0


def _metrics_summary() -> Dict[str, Any] | None:
    settings = get_settings()
    if not settings.log_metrics:
        return None
    path = Path(settings.metrics_jl_path)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()[-50:]
        totals = []
        stt_values = []
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            total = payload.get("total_ms")
            if total is not None:
                totals.append(float(total))
            stt = payload.get("stt_ms")
            if stt is not None:
                stt_values.append(float(stt))
        if not totals:
            return None
        summary = {
            "count": len(totals),
            "avg_total_ms": round(sum(totals) / len(totals), 2),
        }
        if stt_values:
            summary["avg_stt_ms"] = round(sum(stt_values) / len(stt_values), 2)
        return summary
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to read metrics summary: {}", exc)
        return None


def _terms_status() -> Dict[str, Any] | None:
    try:
        store = get_terms_store()
        stats = store.stats()
    except Exception as exc:  # pragma: no cover
        logger.debug("Terms status unavailable: {}", exc)
        return None
    return {
        "count": stats.get("count", 0),
        "loaded_at": stats.get("loaded_at"),
        "fuzzy_enabled": stats.get("fuzzy_enabled", False),
    }


def _elevenlabs_status() -> Dict[str, Any]:
    """ElevenLabs API durumunu kontrol et"""
    try:
        provider = get_eleven_provider(require=False)
        if provider is None:
            return {
                "configured": False,
                "status": "not_configured",
                "message": "ElevenLabs API key not configured"
            }
        
        # API test yap
        voices = provider.list_voices()
        return {
            "configured": True,
            "status": "healthy",
            "voice_count": len(voices),
            "message": "ElevenLabs API is working"
        }
    except Exception as exc:
        logger.debug("ElevenLabs status check failed: {}", exc)
        return {
            "configured": True,
            "status": "error",
            "message": f"ElevenLabs API error: {str(exc)}"
        }


def _resilience_status() -> Dict[str, Any]:
    """Resilience bileşenlerinin durumunu kontrol et"""
    return {
        "circuit_breaker": {"status": "not_implemented", "message": "Circuit breaker not implemented"},
        "heartbeat": {"status": "not_implemented", "message": "Heartbeat monitor not implemented"},
        "queues": {"status": "not_implemented", "message": "Queue monitor not implemented"},
        "watchdog": {"status": "not_implemented", "message": "Watchdog not implemented"}
    }


def _security_status() -> Dict[str, Any]:
    """Güvenlik ayarlarının durumunu kontrol et"""
    settings = get_settings()
    return {
        "api_key_protection": settings.enable_security,
        "rate_limiting": settings.rate_limit_global_rpm > 0,
        "max_upload_mb": settings.max_upload_mb,
        "max_body_mb": settings.max_body_mb,
        "security_protect_all": settings.security_protect_all
    }


def _system_resources() -> Dict[str, Any]:
    """Sistem kaynaklarını kontrol et"""
    import psutil
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_usage_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2)
        }
    except ImportError:
        return {"status": "psutil not available"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/health")
def healthcheck() -> Dict[str, Any]:
    """Kapsamlı uygulama sağlık kontrolü"""
    settings = get_settings()
    torch_cuda = _torch_cuda_available()
    cuda_count = _ctranslate2_cuda_count()
    meta = get_device_metadata()
    configured = settings.device or "auto"
    
    # Determine actual device based on settings
    if configured == "cuda":
        device = "cuda" if (cuda_count > 0 or torch_cuda) else "cpu (fallback)"
    elif configured == "cpu":
        device = "cpu"
    else:  # auto
        device = "cuda" if (cuda_count > 0 or torch_cuda) else "cpu"
    
    fallback_reason = meta.get("fallback_reason")

    # Tüm sağlık kontrollerini yap
    elevenlabs_status = _elevenlabs_status()
    resilience_status = _resilience_status()
    security_status = _security_status()
    system_resources = _system_resources()
    metrics_summary = _metrics_summary()
    terms_status = _terms_status()
    
    # Genel durum belirleme
    overall_status = "healthy"
    issues = []
    
    if elevenlabs_status["status"] == "error":
        overall_status = "degraded"
        issues.append("ElevenLabs API error")
    elif elevenlabs_status["status"] == "not_configured":
        overall_status = "degraded"
        issues.append("ElevenLabs API not configured")
    
    if any(comp["status"] == "error" for comp in resilience_status.values()):
        overall_status = "degraded"
        issues.append("Resilience component error")
    
    if system_resources.get("cpu_usage_percent", 0) > 90:
        overall_status = "degraded"
        issues.append("High CPU usage")
    
    if system_resources.get("memory_usage_percent", 0) > 90:
        overall_status = "degraded"
        issues.append("High memory usage")

    response: Dict[str, Any] = {
        "status": overall_status,
        "timestamp": meta.get("timestamp"),
        "issues": issues,
        
        # Temel sistem bilgileri
        "system": {
            "device": device,
            "configured_device": configured,
            "device_fallback_reason": fallback_reason,
            "torch_cuda": torch_cuda,
            "ctranslate2_cuda": cuda_count > 0,
            "cuda_device_count": cuda_count,
            "ffmpeg": _ffmpeg_version_line(),
            "python_version": platform.python_version(),
            "app_version": "0.1.0"
        },
        
        # Özellikler
        "features": {
            "stt_http": True,
            "stt_ws": True,
            "tts_cloud": True,
            "chain_http": True,
            "chain_ws": True,
        },
        
        # ElevenLabs durumu
        "elevenlabs": elevenlabs_status,
        
        # Resilience durumu
        "resilience": resilience_status,
        
        # Güvenlik durumu
        "security": security_status,
        
        # Sistem kaynakları
        "resources": system_resources,
        
        # Metrikler
        "metrics": metrics_summary or {"status": "not_available"},
        
        # Terimler durumu
        "terms": {
            "loaded": bool(terms_status and terms_status.get("loaded_at")),
            "count": int(terms_status.get("count", 0)) if terms_status else 0,
            "fuzzy_enabled": bool(terms_status.get("fuzzy_enabled", False)) if terms_status else False,
            "loaded_at": terms_status.get("loaded_at") if terms_status else None
        }
    }
    
    return response
