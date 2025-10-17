from __future__ import annotations

import time
from typing import Generator, Iterable, Iterator, TypeVar

from starlette.responses import JSONResponse


T = TypeVar("T")


class WatchdogTimeout(RuntimeError):
    """Raised when a streaming response stalls beyond the configured timeout."""


def wrap_stream(iterable: Iterable[T], write_timeout_sec: float) -> Generator[T, None, None]:
    """Wrap a streaming iterable and raise WatchdogTimeout if gaps exceed the threshold."""
    iterator: Iterator[T] = iter(iterable)
    if write_timeout_sec <= 0:
        yield from iterator
        return
    last = time.monotonic()
    for chunk in iterator:
        now = time.monotonic()
        if now - last > write_timeout_sec:
            raise WatchdogTimeout("write stalled")
        last = now
        yield chunk


def json_timeout_response(detail: str = "write stalled") -> JSONResponse:
    return JSONResponse({"code": "UPSTREAM_TIMEOUT", "detail": detail}, status_code=504)


__all__ = ["WatchdogTimeout", "wrap_stream", "json_timeout_response"]
