from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

import numpy as np
import soundfile as sf
from loguru import logger


class AudioTranscodeError(RuntimeError):
    """Raised when ffmpeg is missing or fails during audio conversion."""


def _ffmpeg_path() -> Path:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise AudioTranscodeError("FFmpeg executable not found in PATH")
    return Path(executable)


def convert_to_wav(
    source: Path,
    target: Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_fmt: str = "s16",
) -> float:
    """
    Transcode ``source`` into a WAV file at ``target`` using FFmpeg.

    Returns the resulting clip duration in seconds.
    """
    ffmpeg = _ffmpeg_path()
    cmd = [
        str(ffmpeg),
        "-y",
        "-i",
        str(source),
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        "-sample_fmt",
        sample_fmt,
        str(target),
    ]
    logger.debug("Running ffmpeg command: {}", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="ignore")
        logger.debug("ffmpeg failed stderr={}", stderr.strip())
        if "Invalid data" in stderr or "unsupported" in stderr.lower():
            raise AudioTranscodeError("FORMAT_UNSUPPORTED")
        raise AudioTranscodeError(f"FFmpeg failed with code {result.returncode}")
    try:
        info = sf.info(str(target))
    except RuntimeError as exc:
        raise AudioTranscodeError(f"Failed to inspect transcoded audio: {exc}") from exc
    if info.samplerate <= 0:
        raise AudioTranscodeError("Invalid samplerate after conversion")
    return float(info.frames) / float(info.samplerate)


def load_wav_int16(path: Path) -> Tuple[np.ndarray, int]:
    """
    Load a WAV file and return samples as int16 numpy array along with sample rate.
    """
    data, sample_rate = sf.read(str(path), dtype="int16")
    if data.ndim > 1:
        data = data[:, 0]
    return data.astype(np.int16, copy=False), int(sample_rate)


__all__ = ["AudioTranscodeError", "convert_to_wav", "load_wav_int16"]
