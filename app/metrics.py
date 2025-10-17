from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from app.config import get_settings


class Span:
    def __init__(self) -> None:
        self.start = time.perf_counter()
        self.end: Optional[float] = None

    def stop(self) -> float:
        if self.end is None:
            self.end = time.perf_counter()
        return (self.end - self.start) * 1000.0

    @property
    def duration_ms(self) -> float:
        return self.stop()


def now_ms() -> int:
    return int(time.time() * 1000)


def log_metrics(entry: Dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.log_metrics:
        return
    path = Path(settings.metrics_jl_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry.setdefault("ts", now_ms())
    try:
        with path.open("a", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False)
            handle.write("\n")
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to append metrics: {}", exc)
