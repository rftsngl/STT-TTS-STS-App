from __future__ import annotations
import time

from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.metrics_reader import (
    iter_events,
    parse_window,
    window_filter,
    summarize,
    redact_sensitive,
    parse_timestamp,
)


router = APIRouter(prefix="/diag", tags=["diagnostics"])


def _ensure_positive(name: str, value: int) -> int:
    if value <= 0:
        raise HTTPException(status_code=400, detail=f"{name} must be positive")
    return value


def _group_by_from_param(param: str) -> Tuple[str, ...]:
    items = [part.strip() for part in param.split(",") if part.strip()]
    return tuple(items or ["route"])


def _prepare_events(
    tail_bytes: Optional[int],
    window_seconds: Optional[float],
    limit: int,
) -> Iterable[dict]:
    settings = get_settings()
    metrics_path = Path(settings.metrics_jl_path)
    events_iter = iter_events(metrics_path, tail_bytes)
    since_epoch: Optional[float] = None
    if window_seconds:
        since_epoch = time.time() - window_seconds
    return window_filter(events_iter, since_epoch=since_epoch, limit=limit)


def _format_ts(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


@router.get("/metrics/summary")
async def metrics_summary(
    window: str = Query("5m"),
    tail_bytes: int = Query(10 * 1024 * 1024),
    group_by: str = Query("route"),
    limit: Optional[int] = Query(None),
):
    settings = get_settings()
    window_seconds = parse_window(window)
    if window_seconds is None:
        raise HTTPException(status_code=400, detail="Invalid window value")
    tail_bytes = _ensure_positive("tail_bytes", tail_bytes)
    max_rows = settings.metrics_summary_max_rows
    effective_limit = min(limit or max_rows, max_rows)
    group_fields = _group_by_from_param(group_by)
    events = list(_prepare_events(tail_bytes, window_seconds, effective_limit))
    summary = summarize(events, group_by=group_fields)
    cb_counts: Dict[str, int] = defaultdict(int)
    for event in events:
        state = event.get("cb_state")
        if isinstance(state, str) and state:
            cb_counts[state] += 1
    if cb_counts:
        summary["cb_state_counts"] = dict(sorted(cb_counts.items()))
    summary["window"] = window
    summary["tail_bytes"] = tail_bytes
    summary["limit"] = effective_limit
    return summary


@router.get("/metrics/last")
async def metrics_last(
    n: int = Query(50, ge=1, le=1000),
    tail_bytes: int = Query(10 * 1024 * 1024),
):
    settings = get_settings()
    metrics_path = Path(settings.metrics_jl_path)
    tail_bytes = _ensure_positive("tail_bytes", tail_bytes)
    events_iter = iter_events(metrics_path, tail_bytes)
    buffer: deque[dict] = deque(maxlen=n)
    for event in events_iter:
        buffer.append(event)
    ordered_events = sorted(buffer, key=lambda item: parse_timestamp(item.get("ts")) or 0.0, reverse=True)
    redacted = []
    for event in ordered_events:
        event.pop("_ts", None)
        redacted.append(redact_sensitive(event))
    return redacted


@router.get("/errors/summary")
async def errors_summary(
    window: str = Query("15m"),
    tail_bytes: int = Query(10 * 1024 * 1024),
    limit: Optional[int] = Query(None),
    examples: int = Query(10, ge=1, le=50),
):
    settings = get_settings()
    window_seconds = parse_window(window)
    if window_seconds is None:
        raise HTTPException(status_code=400, detail="Invalid window value")
    tail_bytes = _ensure_positive("tail_bytes", tail_bytes)
    max_rows = settings.metrics_summary_max_rows
    effective_limit = min(limit or max_rows, max_rows)
    events = _prepare_events(tail_bytes, window_seconds, effective_limit)

    http_counts: Dict[int, int] = defaultdict(int)
    code_counts: Dict[str, int] = defaultdict(int)
    example_events: List[Dict[str, Any]] = []

    for event in events:
        status = event.get("http_status")
        error_code = event.get("error_code")
        has_error = False
        if isinstance(status, int) and status >= 400:
            http_counts[status] += 1
            has_error = True
        if isinstance(error_code, str) and error_code:
            code_counts[error_code] += 1
            has_error = True
        if has_error:
            example_events.append(event)

    example_events.sort(key=lambda item: item.get("_ts", 0.0), reverse=True)
    clipped_examples = []
    for event in example_events[:examples]:
        clipped_examples.append(
            {
                "ts": _format_ts(event.get("_ts")),
                "route": event.get("route"),
                "http_status": event.get("http_status"),
                "error_code": event.get("error_code"),
                "notes": event.get("notes") or event.get("message") or "",
            }
        )

    return {
        "window": window,
        "http_status_counts": dict(sorted(http_counts.items())),
        "error_code_counts": dict(sorted(code_counts.items(), key=lambda item: item[1], reverse=True)),
        "examples": clipped_examples,
    }
