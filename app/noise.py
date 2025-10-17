from __future__ import annotations

import math
from typing import Optional

import numpy as np
from loguru import logger

from app.config import Settings, get_settings

try:
    import noisereduce as nr  # type: ignore

    HAVE_NOISEREDUCE = True
except Exception:  # pragma: no cover
    HAVE_NOISEREDUCE = False

try:  # pragma: no cover
    import rnnoise  # type: ignore

    HAVE_RNNOISE = True
except Exception:
    HAVE_RNNOISE = False

_WARNED_SPECTRAL = False
_WARNED_RNNOISE = False


def _spectral_params(strength: str) -> dict:
    strength = strength.lower()
    if strength == "low":
        return {"prop_decrease": 0.75, "n_std_thresh_stationary": 1.5}
    if strength == "high":
        return {"prop_decrease": 1.0, "n_std_thresh_stationary": 0.8}
    return {"prop_decrease": 0.9, "n_std_thresh_stationary": 1.0}


def reduce_noise_offline(samples: np.ndarray, sample_rate: int, settings: Optional[Settings] = None) -> np.ndarray:
    settings = settings or get_settings()
    mode = settings.noise_suppressor
    if mode == "spectral":
        global _WARNED_SPECTRAL  # pragma: no cover - module state
        if not HAVE_NOISEREDUCE:
            if not _WARNED_SPECTRAL:
                logger.warning("## WARN: spectral off (noisereduce package not available)")
                _WARNED_SPECTRAL = True
            return samples
        params = _spectral_params(settings.ns_strength)
        try:
            reduced = nr.reduce_noise(y=samples.astype(np.float32), sr=sample_rate, **params)
            return reduced.astype(samples.dtype)
        except Exception as exc:
            logger.warning("## WARN: spectral off (fallback) - {}", exc)
            return samples
    elif mode == "rnnoise":
        global _WARNED_RNNOISE
        if not HAVE_RNNOISE:
            if not _WARNED_RNNOISE:
                logger.warning("## WARN: rnnoise off (module not available)")
                _WARNED_RNNOISE = True
            return samples
        try:
            frame_size = 480  # 30 ms at 16 kHz
            processed = []
            state = rnnoise.RNNoise()
            for i in range(0, len(samples), frame_size):
                frame = samples[i : i + frame_size]
                if len(frame) < frame_size:
                    pad = np.zeros(frame_size, dtype=frame.dtype)
                    pad[: len(frame)] = frame
                    frame = pad
                processed.append(state.filter(frame.astype(np.float32)))
            if not processed:
                return samples
            reduced = np.concatenate(processed)[: len(samples)]
            return reduced.astype(samples.dtype)
        except Exception as exc:
            logger.warning("## WARN: rnnoise off (processing failed) - {}", exc)
            return samples
    return samples


class NoiseGate:
    def __init__(self, sample_rate: int, warmup_frames: int = 30) -> None:
        self.sample_rate = sample_rate
        self.warmup_frames = warmup_frames
        self.noise_floor: Optional[float] = None
        self.frame_index = 0

    def allow(self, frame: np.ndarray) -> bool:
        energy = float(np.sqrt(np.mean(np.square(frame.astype(np.float32))) + 1e-12))
        if self.noise_floor is None:
            self.noise_floor = energy
        else:
            alpha = 0.95
            self.noise_floor = alpha * self.noise_floor + (1 - alpha) * energy
        threshold = (self.noise_floor or energy) * 2.5
        self.frame_index += 1
        if self.frame_index < self.warmup_frames:
            return True
        return energy >= threshold


def gate_streaming_frame(frame: np.ndarray, gate: NoiseGate) -> bool:
    return gate.allow(frame)
