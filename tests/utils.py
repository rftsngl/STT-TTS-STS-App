from __future__ import annotations

import math
import os
import socket
import tempfile
import time
import wave
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional

import numpy as np
import requests



def ensure_reports_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def find_free_port(preferred: Optional[int] = None) -> int:
    if preferred:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", preferred))
                return preferred
            except OSError:
                pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def make_tone_wav(target: Path, sr: int = 16000, secs: float = 1.0, freq: float = 1000.0) -> Path:
    samples = int(sr * secs)
    t = np.linspace(0, secs, samples, endpoint=False)
    waveform = 0.15 * np.sin(2 * math.pi * freq * t)
    pcm = np.int16(np.clip(waveform, -1.0, 1.0) * 32767)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return target


def pcm20ms_blocks(wav_path: Path, block_ms: int = 20) -> Iterator[bytes]:
    with wave.open(str(wav_path), "rb") as wf:
        sr = wf.getframerate()
        sample_width = wf.getsampwidth()
        frame_count = wf.getnframes()
        samples_per_block = max(1, int(sr * (block_ms / 1000.0)))
        bytes_per_block = samples_per_block * sample_width
        frames_read = 0
        while frames_read < frame_count:
            data = wf.readframes(samples_per_block)
            frames_read += samples_per_block
            if not data:
                break
            yield data


def mask(value: Optional[str]) -> str:
    if not value:
        return "***"
    visible = value[:4]
    return f"{visible}***"


class HTTPClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.api_key = api_key

    def _headers(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        merged: Dict[str, str] = {}
        if headers:
            merged.update(headers)
        if self.api_key:
            merged.setdefault("X-API-Key", self.api_key)
        return merged

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", None)
        kwargs["headers"] = self._headers(headers)
        return self.session.request(method, url, **kwargs)

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)




def wait_for(condition, timeout: float = 10.0, interval: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


__all__ = [
    "HTTPClient",
    "ensure_reports_dir",
    "find_free_port",
    "make_tone_wav",
    "mask",
    "pcm20ms_blocks",
    "wait_for",
]
