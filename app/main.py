import warnings
# CTranslate2'nin pkg_resources uyarısını sustur
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")

from fastapi import FastAPI, Request
from app.config import get_settings
from app.security.api_key import APIKeyMiddleware, is_enabled
from app.security.body_limit import BodyLimitMiddleware
from app.security.rate_limit import RateLimitMiddleware
from app.resilience.watchdog import WatchdogTimeout, json_timeout_response

from app.chain_http import router as chain_http_router
from app.health import router as health_router
from app.ivc_api import router as ivc_router
from app.stt import router as stt_router
from app.tts_cloud import router as tts_router
from app.voices_api import router as voices_router
from app.diag_routes import router as diag_router
from app.diag_metrics import router as diag_metrics_router
from app.terms_api import router as terms_router
from app.ui_admin import router as ui_router
from app.audio_isolation import router as audio_isolation_router


app = FastAPI(title="TR Speech Stack", version="0.1.0")
settings = get_settings()

if is_enabled(settings):
    app.add_middleware(APIKeyMiddleware)
app.add_middleware(BodyLimitMiddleware, max_upload_mb=settings.max_upload_mb, max_body_mb=settings.max_body_mb)
app.add_middleware(RateLimitMiddleware, global_rpm=settings.rate_limit_global_rpm, ip_rpm=settings.rate_limit_ip_rpm, burst_factor=settings.rate_bucket_burst)


@app.exception_handler(WatchdogTimeout)
async def _watchdog_timeout_handler(request: Request, exc: WatchdogTimeout):
    return json_timeout_response()

app.include_router(health_router)
app.include_router(stt_router)
app.include_router(tts_router)
app.include_router(voices_router)
app.include_router(ivc_router)
app.include_router(chain_http_router)
app.include_router(terms_router)
app.include_router(diag_router)
app.include_router(diag_metrics_router)
app.include_router(ui_router)
app.include_router(audio_isolation_router)

__all__ = ["app"]
