from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple, Dict, Any


@dataclass
class MetricEvent:
    ts: float
    route: str
    total_ms: Optional[float] = None
    stt_ms: Optional[float] = None
    tts_stream_ms: Optional[float] = None
    vad_ms: Optional[float] = None
    noise_ms: Optional[float] = None
    device: str = "unknown"
    compute_type: str = "unknown"
    model: str = "unknown"
    http_status: Optional[int] = None
    error_code: Optional[str] = None
    provider: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)


def parse_line(raw: str) -> Optional[dict]:
    raw = raw.strip()
    if not raw:
        return None
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        return None
    return None


def _open_for_tail(path: Path, tail_bytes: Optional[int]) -> Iterable[str]:
    with path.open("r", encoding="utf-8") as handle:
        if tail_bytes is not None:
            try:
                handle.seek(0, os.SEEK_END)
                file_size = handle.tell()
                seek_pos = max(file_size - tail_bytes, 0)
                handle.seek(seek_pos, os.SEEK_SET)
                if seek_pos > 0:
                    handle.readline()
            except OSError:
                handle.seek(0)
        for line in handle:
            yield line


def iter_events(path: Path, tail_bytes: Optional[int] = None) -> Iterator[dict]:
    if not path.exists():
        return iter(())
    return (event for event in (parse_line(line) for line in _open_for_tail(path, tail_bytes)) if event)


def parse_timestamp(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return None
    return None


def _format_timestamp(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def parse_window(window: str) -> Optional[float]:
    if not window:
        return None
    window = window.strip().lower()
    try:
        if window.endswith("ms"):
            return float(window[:-2]) / 1000.0
        if window.endswith("s"):
            return float(window[:-1])
        if window.endswith("m"):
            return float(window[:-1]) * 60.0
        if window.endswith("h"):
            return float(window[:-1]) * 3600.0
        return float(window)
    except ValueError:
        return None


def window_filter(events: Iterable[dict], since_epoch: Optional[float] = None, limit: Optional[int] = None) -> Iterator[dict]:
    count = 0
    for event in events:
        if limit is not None and count >= limit:
            break
        ts_value = parse_timestamp(event.get("ts"))
        if ts_value is None:
            continue
        if since_epoch is not None and ts_value < since_epoch:
            continue
        event["_ts"] = ts_value
        yield event
        count += 1


def quantiles(samples: Sequence[float], quantile_points: Sequence[float]) -> Dict[float, Optional[float]]:
    if not samples:
        return {q: None for q in quantile_points}
    sorted_samples = sorted(samples)
    n = len(sorted_samples)
    results: Dict[float, Optional[float]] = {}
    for q in quantile_points:
        if not 0 <= q <= 1:
            results[q] = None
            continue
        if n == 1:
            results[q] = float(sorted_samples[0])
            continue
        pos = q * (n - 1)
        lower_index = int(math.floor(pos))
        upper_index = int(math.ceil(pos))
        fraction = pos - lower_index
        lower = sorted_samples[lower_index]
        upper = sorted_samples[upper_index]
        results[q] = float(lower + (upper - lower) * fraction)
    return results


def _budget_targets() -> Dict[str, float]:
    return {
        "TARGET_TOTAL_MS": float(os.environ.get("TARGET_TOTAL_MS", "250")),
        "TARGET_STT_MS": float(os.environ.get("TARGET_STT_MS", "120")),
        "TARGET_TTS_MS": float(os.environ.get("TARGET_TTS_MS", "120")),
    }


def _extract_metric(event: dict, key: str) -> Optional[float]:
    value = event.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize(
    events: Iterable[dict],
    group_by: Tuple[str, ...] = ("route",),
    fields: Tuple[str, ...] = ("total_ms", "stt_ms", "tts_stream_ms", "vad_ms"),
) -> Dict[str, Any]:
    budgets = _budget_targets()
    quant_points = (0.5, 0.9, 0.95, 0.99)
    groups: Dict[Tuple, Dict[str, Any]] = {}
    total_rows = 0

    for event in events:
        total_rows += 1
        key_values = []
        for field in group_by:
            value = event.get(field, "unknown")
            if value is None:
                value = "unknown"
            key_values.append(value)
        key = tuple(key_values)
        bucket = groups.setdefault(
            key,
            {
                "count": 0,
                "metrics": {field: [] for field in fields},
                "over_budget": {field: 0 for field in fields},
                "http_status": {},
                "error_codes": {},
                "ts_first": None,
                "ts_last": None,
            },
        )
        bucket["count"] += 1
        for field in fields:
            value = _extract_metric(event, field)
            if value is not None:
                bucket["metrics"][field].append(value)
                target_name = {
                    "total_ms": "TARGET_TOTAL_MS",
                    "stt_ms": "TARGET_STT_MS",
                    "tts_stream_ms": "TARGET_TTS_MS",
                }.get(field)
                if target_name and value > budgets.get(target_name, float("inf")):
                    bucket["over_budget"][field] += 1
        status = event.get("http_status")
        if isinstance(status, int):
            bucket["http_status"][status] = bucket["http_status"].get(status, 0) + 1
        error_code = event.get("error_code")
        if isinstance(error_code, str) and error_code:
            bucket["error_codes"][error_code] = bucket["error_codes"].get(error_code, 0) + 1
        ts = event.get("_ts")
        if ts is not None:
            bucket["ts_first"] = ts if bucket["ts_first"] is None else min(bucket["ts_first"], ts)
            bucket["ts_last"] = ts if bucket["ts_last"] is None else max(bucket["ts_last"], ts)

    summary_groups: List[Dict[str, Any]] = []
    for key, bucket in groups.items():
        metrics_summary: Dict[str, Any] = {}
        for field in fields:
            samples = bucket["metrics"].get(field, [])
            q_values = quantiles(samples, quant_points) if samples else {q: None for q in quant_points}
            mean_value = float(sum(samples) / len(samples)) if samples else None
            over_budget_count = bucket["over_budget"].get(field, 0)
            over_budget_pct = (over_budget_count / len(samples) * 100.0) if samples else 0.0
            metrics_summary[field] = {
                "p50": q_values[0.5],
                "p90": q_values[0.9],
                "p95": q_values[0.95],
                "p99": q_values[0.99],
                "mean": mean_value,
                "budget_over_pct": over_budget_pct,
            }
        key_dict = {field: value for field, value in zip(group_by, key)}
        summary_groups.append(
            {
                "key": key_dict,
                "n": bucket["count"],
                "latency": metrics_summary,
                "errors": {
                    "http": bucket["http_status"],
                    "codes": bucket["error_codes"],
                },
                "ts": {
                    "first": _format_timestamp(bucket["ts_first"]),
                    "last": _format_timestamp(bucket["ts_last"]),
                },
            }
        )

    summary_groups.sort(key=lambda item: item["n"], reverse=True)
    return {
        "count": total_rows,
        "groups": summary_groups,
        "budgets": budgets,
    }


def redact_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    redacted = {}
    for key, value in data.items():
        if isinstance(key, str) and "api_key" in key.lower():
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted
