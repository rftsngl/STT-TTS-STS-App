from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Iterable, List

import numpy as np
import webrtcvad


FRAME_DURATION_MS = 20


def pcm16le_to_float32(pcm: bytes) -> np.ndarray:
    if not pcm:
        return np.empty(0, dtype=np.float32)
    array = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    return array / 32768.0


def float32_to_pcm16le(samples: np.ndarray) -> bytes:
    if samples.size == 0:
        return b""
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype(np.int16).tobytes()


@dataclass
class AudioFrame:
    start: float
    end: float
    pcm: bytes
    samples: np.ndarray
    is_speech: bool


class CircularAudioBuffer:
    def __init__(self, max_seconds: float) -> None:
        self.max_seconds = max_seconds
        self._frames: Deque[AudioFrame] = deque()

    def append(self, frame: AudioFrame) -> None:
        self._frames.append(frame)
        self._trim_old(frame.end)

    def _trim_old(self, latest_end: float) -> None:
        while self._frames and latest_end - self._frames[0].start > self.max_seconds:
            self._frames.popleft()

    def drop_until(self, timestamp: float) -> None:
        while self._frames and self._frames[0].end <= timestamp:
            self._frames.popleft()

    def frames(self) -> Iterable[AudioFrame]:
        return tuple(self._frames)


class VADTracker:
    def __init__(self, sample_rate: int, aggressiveness: int, endpoint_silence_ms: int) -> None:
        self.sample_rate = sample_rate
        self.frame_duration_ms = FRAME_DURATION_MS
        self.endpoint_silence_ms = endpoint_silence_ms
        self._vad = webrtcvad.Vad(min(max(aggressiveness, 0), 3))
        self._silence_acc = 0
        self._in_speech = False

    def process(self, frame: bytes) -> tuple[bool, str]:
        try:
            voiced = self._vad.is_speech(frame, self.sample_rate)
        except Exception:
            voiced = False

        if voiced:
            self._silence_acc = 0
            if not self._in_speech:
                self._in_speech = True
                return True, "begin"
            return True, "speech"

        if self._in_speech:
            self._silence_acc += self.frame_duration_ms
            if self._silence_acc >= self.endpoint_silence_ms:
                self._in_speech = False
                self._silence_acc = 0
                return False, "end"
            return False, "speech"

        return False, "silence"

    @property
    def in_speech(self) -> bool:
        return self._in_speech


def merge_frames(frames: Iterable[AudioFrame]) -> np.ndarray:
    arrays: List[np.ndarray] = [frame.samples for frame in frames if frame.samples.size > 0]
    if not arrays:
        return np.empty(0, dtype=np.float32)
    return np.concatenate(arrays)
