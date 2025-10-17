from __future__ import annotations

import time
from collections import defaultdict
from secrets import compare_digest
from threading import Lock
from typing import Dict, Hashable, Optional

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings
from app.security.errors import json_error


class TokenBucket:
    __slots__ = ("refill_rate", "capacity", "tokens", "updated")

    def __init__(self, rate_per_minute: float, burst_factor: float) -> None:
        rate_per_second = max(rate_per_minute / 60.0, 0.01)
        capacity = max(rate_per_second * burst_factor, 1.0)
        self.refill_rate = rate_per_second
        self.capacity = capacity
        self.tokens = capacity
        self.updated = time.monotonic()

    def consume(self, amount: float = 1.0) -> bool:
        now = time.monotonic()
        elapsed = now - self.updated
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.updated = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class _LimiterState:
    def __init__(self, rate_per_minute: float, burst: float) -> None:
        self.rate_per_minute = rate_per_minute
        self.burst = burst
        self._buckets: Dict[Hashable, TokenBucket] = {}
        self._lock = Lock()
        self._last_log: Dict[Hashable, float] = defaultdict(float)

    def consume(self, key: Hashable, amount: float = 1.0) -> bool:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(self.rate_per_minute, self.burst)
                self._buckets[key] = bucket
            return bucket.consume(amount)

    def remove(self, key: Hashable) -> None:
        with self._lock:
            self._buckets.pop(key, None)
            self._last_log.pop(key, None)

    def log_once(self, key: Hashable, message: str, interval: float = 10.0) -> None:
        now = time.monotonic()
        last = self._last_log.get(key, 0.0)
        if now - last >= interval:
            logger.info(message)
            self._last_log[key] = now


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        global_rpm: float,
        ip_rpm: float,
        burst_factor: float,
    ) -> None:
        super().__init__(app)
        self.global_limiter = _LimiterState(global_rpm, burst_factor)
        self.ip_limiter = _LimiterState(ip_rpm, burst_factor)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        path = request.url.path
        if path.startswith('/ui') or path == '/' or path == '/favicon.ico':
            return await call_next(request)


        if not self.global_limiter.consume("GLOBAL"):
            self.global_limiter.log_once("GLOBAL", "## Global rate limit exceeded")
            return json_error(429, "RATE_LIMIT", "Too many requests")
        if not self.ip_limiter.consume(client_ip):
            self.ip_limiter.log_once(client_ip, f"## Rate limit exceeded ip={client_ip}")
            return json_error(429, "RATE_LIMIT", "Too many requests from this client")
        return await call_next(request)


