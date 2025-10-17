from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Generic, Optional, Tuple, TypeVar


T = TypeVar("T")


@dataclass
class QueueStats:
    depth: int
    max_depth: int
    dropped: int
    avg_wait_ms: float
    total_wait_ms: float
    count: int


class BoundedQueue(Generic[T]):
    """Non-blocking bounded queue that tracks basic metrics for resilience."""

    __slots__ = (
        "_maxsize",
        "_items",
        "_available",
        "dropped_count",
        "max_depth",
        "_total_wait_ms",
        "_dequeue_count",
    )

    def __init__(self, maxsize: int) -> None:
        self._maxsize = max(1, int(maxsize))
        self._items: Deque[Tuple[float, T]] = deque()
        self._available = asyncio.Event()
        self.dropped_count = 0
        self.max_depth = 0
        self._total_wait_ms = 0.0
        self._dequeue_count = 0

    def offer(self, item: T, *, force: bool = False) -> bool:
        """Attempt to enqueue without blocking."""
        if len(self._items) >= self._maxsize:
            if not force:
                self.dropped_count += 1
                return False
            # drop the oldest item to make room
            self._items.popleft()
            self.dropped_count += 1
        self._items.append((time.monotonic(), item))
        size = len(self._items)
        if size > self.max_depth:
            self.max_depth = size
        self._available.set()
        return True

    def try_get(self) -> Tuple[bool, Optional[T], float]:
        """Attempt to dequeue without waiting."""
        if not self._items:
            return False, None, 0.0
        enqueued_at, item = self._items.popleft()
        wait_ms = (time.monotonic() - enqueued_at) * 1000.0
        self._total_wait_ms += wait_ms
        self._dequeue_count += 1
        if not self._items:
            self._available.clear()
        return True, item, wait_ms

    async def get(self) -> Tuple[T, float]:
        """Wait until an item is available and dequeue it."""
        success, item, wait_ms = self.try_get()
        if success:
            return item, wait_ms
        while True:
            await self._available.wait()
            success, item, wait_ms = self.try_get()
            if success:
                return item, wait_ms

    def stats(self) -> QueueStats:
        avg = self._total_wait_ms / self._dequeue_count if self._dequeue_count else 0.0
        return QueueStats(
            depth=len(self._items),
            max_depth=self.max_depth,
            dropped=self.dropped_count,
            avg_wait_ms=avg,
            total_wait_ms=self._total_wait_ms,
            count=self._dequeue_count,
        )

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._items)
