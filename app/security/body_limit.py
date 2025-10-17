from __future__ import annotations

from typing import Optional

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.security.errors import json_error


class _PayloadTooLarge(Exception):
    __slots__ = ("size",)

    def __init__(self, size: int) -> None:
        super().__init__("payload too large")
        self.size = size


class BodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_upload_mb: int, max_body_mb: int) -> None:
        super().__init__(app)
        self.max_upload_bytes = max(1, int(max_upload_mb)) * 1024 * 1024
        self.max_body_bytes = max(1, int(max_body_mb)) * 1024 * 1024

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method.upper()
        if method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        content_type = (request.headers.get("content-type") or "").lower()
        limit_bytes = self.max_upload_bytes if content_type.startswith("multipart/form-data") else self.max_body_bytes

        content_length = self._content_length(request)
        if content_length is not None and content_length > limit_bytes:
            logger.info(
                "## Payload rejected by length header method={} path={} length={}",
                method,
                request.url.path,
                content_length,
            )
            return self._too_large()

        try:
            return await self._call_with_body_limit(request, call_next, limit_bytes)
        except _PayloadTooLarge as exc:
            logger.info(
                "## Payload rejected after streaming method={} path={} size~{}",
                method,
                request.url.path,
                exc.size,
            )
            return self._too_large()

    async def _call_with_body_limit(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
        limit_bytes: int,
    ) -> Response:
        original_receive = request._receive  # type: ignore[attr-defined]
        total = 0

        async def limited_receive() -> dict:
            nonlocal total
            message = await original_receive()
            if message["type"] != "http.request":
                return message
            body = message.get("body", b"")
            if body:
                total += len(body)
                if total > limit_bytes:
                    raise _PayloadTooLarge(total)
            return message

        request._receive = limited_receive  # type: ignore[attr-defined]
        try:
            return await call_next(request)
        finally:
            request._receive = original_receive  # type: ignore[attr-defined]

    @staticmethod
    def _content_length(request: Request) -> Optional[int]:
        raw = request.headers.get("content-length")
        if raw is None:
            return None
        try:
            value = int(raw)
            if value < 0:
                return None
            return value
        except ValueError:
            return None

    @staticmethod
    def _too_large() -> Response:
        return json_error(413, "PAYLOAD_TOO_LARGE", "Payload too large")
