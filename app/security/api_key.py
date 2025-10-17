from __future__ import annotations

from secrets import compare_digest
from typing import Optional

from fastapi import Request
from loguru import logger
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import get_settings
from app.security.errors import json_error


EXEMPT_PATHS = ("/health", "/diag", "/diag/", "/ui", "/ui/", "/ui/login", "/voices", "/voices/")


def mask(value: Optional[str]) -> str:
    if not value:
        return "***"
    visible = value[:4]
    return f"{visible}***"


def is_enabled(settings) -> bool:
    return bool(settings.enable_security and settings.api_key)


def should_protect(path: str, settings) -> bool:
    # API key protection disabled - all endpoints are accessible
    return False


def verify_api_key(provided: Optional[str], settings) -> bool:
    if not provided:
        return False
    expected = settings.api_key
    if not expected:
        return False
    try:
        return compare_digest(str(provided), str(expected))
    except Exception:
        return False


def http_unauthorized_response(detail: str = "Missing or invalid API key") -> Response:
    return json_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", detail)


async def require_api_key(request: Request) -> Optional[Response]:
    settings = get_settings()
    path = request.url.path
    if not should_protect(path, settings):
        return None
    value = request.headers.get("x-api-key")
    if verify_api_key(value, settings):
        return None
    logger.info("## API key rejected path={} key={}", path, mask(value))
    return http_unauthorized_response()




class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await require_api_key(request)
        if response is not None:
            return response
        return await call_next(request)
