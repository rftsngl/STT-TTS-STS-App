from __future__ import annotations

from secrets import compare_digest
from typing import TYPE_CHECKING, Optional

from fastapi import Request
from loguru import logger
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import get_settings
from app.security.errors import json_error

if TYPE_CHECKING:
    from app.config import Settings

# Paths that don't require authentication
EXEMPT_PATHS = (
    "/health",
    "/diag",
    "/diag/",
    "/ui",
    "/ui/",
    "/ui/login",
    "/ui/api/auth/login",
    "/ui/api/config/elevenlabs-key",
    "/voices",
    "/voices/",
)


def mask(value: Optional[str]) -> str:
    if not value:
        return "***"
    visible = value[:4]
    return f"{visible}***"


def is_enabled(settings: Settings) -> bool:
    return bool(settings.enable_security and settings.api_key)


def should_protect(path: str, settings: Settings) -> bool:
    """
    Determine if a path should be protected by API key authentication.

    Returns True if the path requires authentication, False otherwise.
    """
    # Check if path is in exempt list
    for exempt_path in EXEMPT_PATHS:
        if path.startswith(exempt_path):
            return False

    # If security is disabled, don't protect any paths
    if not settings.enable_security:
        return False

    # Protect all other paths
    return True


def verify_api_key(provided: Optional[str], settings: Settings) -> bool:
    """Verify internal API key for admin operations."""
    if not provided:
        return False
    expected = settings.api_key
    if not expected:
        return False
    try:
        return compare_digest(str(provided), str(expected))
    except Exception:
        return False


def verify_elevenlabs_key(provided: Optional[str]) -> bool:
    """
    Verify ElevenLabs API key format.

    This performs basic format validation. Actual API validation
    happens when the key is used with ElevenLabs API.
    """
    if not provided:
        return False

    # ElevenLabs keys start with "sk_" and are at least 20 characters
    if not provided.startswith("sk_"):
        return False

    if len(provided) < 20:
        return False

    return True


def has_valid_elevenlabs_key(request: Request) -> bool:
    """
    Check if request has a valid ElevenLabs API key in headers.

    This is used for session-based authentication where the user
    provides their own ElevenLabs API key.

    Note: No fallback to .env file - only checks header.
    """
    # Check X-ElevenLabs-Key header only (no .env fallback)
    elevenlabs_key = request.headers.get("X-ElevenLabs-Key")
    if elevenlabs_key and verify_elevenlabs_key(elevenlabs_key):
        return True

    return False


def http_unauthorized_response(detail: str = "Missing or invalid API key") -> Response:
    return json_error(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", detail)


async def require_api_key(request: Request) -> Optional[Response]:
    """
    Middleware function to check API key authentication.

    Authentication methods (in order of priority):
    1. X-ElevenLabs-Key header (user's own ElevenLabs API key)
    2. X-API-Key header (internal API key for admin operations)

    Returns None if authentication succeeds, Response with 401 if it fails.
    """
    settings = get_settings()
    path = request.url.path

    # Check if path should be protected
    if not should_protect(path, settings):
        return None

    # Method 1: Check for ElevenLabs API key (user authentication)
    if has_valid_elevenlabs_key(request):
        return None

    # Method 2: Check for internal API key (admin authentication)
    internal_key = request.headers.get("x-api-key")
    if verify_api_key(internal_key, settings):
        return None

    # Authentication failed
    logger.info("## API key rejected path={} elevenlabs_key={} internal_key={}",
                path,
                mask(request.headers.get("X-ElevenLabs-Key")),
                mask(internal_key))
    return http_unauthorized_response("Missing or invalid API key. Please provide X-ElevenLabs-Key or X-API-Key header.")


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await require_api_key(request)
        if response is not None:
            return response
        return await call_next(request)
