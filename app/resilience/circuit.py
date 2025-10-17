from __future__ import annotations

import random
import time
from collections import deque
from enum import Enum
from threading import Lock
from typing import Deque, Dict, Optional, Tuple

from loguru import logger


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_ratio: float,
        window: int,
        cooldown_ms: int,
        half_open_max: int,
        name: str,
    ) -> None:
        self._failure_ratio = max(0.0, min(1.0, float(failure_ratio)))
        self._window = max(1, int(window))
        self._cooldown_ms = max(0, int(cooldown_ms))
        self._half_open_max = max(1, int(half_open_max))
        self._name = name
        self._state = CircuitState.CLOSED
        self._lock = Lock()
        self._events: Deque[bool] = deque(maxlen=self._window)
        self._opened_at: Optional[float] = None
        self._half_open_inflight = 0
        self._last_logged_state: Optional[CircuitState] = None

    def allow_request(self) -> Tuple[bool, bool]:
        with self._lock:
            now = time.monotonic()
            if self._state == CircuitState.OPEN:
                if self._opened_at is None:
                    self._opened_at = now
                elapsed_ms = (now - self._opened_at) * 1000.0
                if elapsed_ms >= self._cooldown_ms:
                    self._transition(CircuitState.HALF_OPEN)
                    self._half_open_inflight = 0
                else:
                    return False, False

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_inflight >= self._half_open_max:
                    return False, False
                self._half_open_inflight += 1
                return True, True

            return True, False

    def record_success(self, probe: bool = False) -> None:
        with self._lock:
            self._events.append(True)
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_inflight = max(0, self._half_open_inflight - 1)
                if self._half_open_inflight == 0:
                    self._transition(CircuitState.CLOSED)
                    self._events.clear()

    def record_failure(self, kind: str, probe: bool = False) -> None:
        with self._lock:
            self._events.append(False)
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_inflight = max(0, self._half_open_inflight - 1)
                self._open_circuit()
                return
            if self._should_open():
                self._open_circuit()

    def jitter_delay(self, base_delay: float, jitter_ms: int) -> float:
        if jitter_ms <= 0:
            return base_delay
        return base_delay + random.uniform(0.0, jitter_ms / 1000.0)

    def state(self) -> CircuitState:
        with self._lock:
            return self._state

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            now = time.monotonic()
            cooldown_left = 0.0
            if self._state == CircuitState.OPEN and self._opened_at is not None:
                cooldown_left = max(
                    0.0,
                    self._cooldown_ms - (now - self._opened_at) * 1000.0,
                )
            failure_count = sum(1 for item in self._events if not item)
            ratio = (failure_count / len(self._events)) if self._events else 0.0
            return {
                "name": self._name,
                "state": self._state.value,
                "failure_ratio": round(ratio, 3),
                "window": len(self._events),
                "cooldown_ms_left": int(cooldown_left),
                "half_open_inflight": self._half_open_inflight,
            }

    def _should_open(self) -> bool:
        if len(self._events) < self._window:
            return False
        failures = sum(1 for item in self._events if not item)
        ratio = failures / len(self._events)
        return ratio >= self._failure_ratio

    def _open_circuit(self) -> None:
        self._transition(CircuitState.OPEN)
        self._opened_at = time.monotonic()
        self._half_open_inflight = 0

    def _transition(self, state: CircuitState) -> None:
        if self._state == state:
            return
        self._state = state
        if self._last_logged_state != state:
            snapshot = self.snapshot()
            logger.info("## circuit %s transitioned to %s (failure_ratio=%.2f)", self._name, state.value, snapshot["failure_ratio"])
            self._last_logged_state = state
