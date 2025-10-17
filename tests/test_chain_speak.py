from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_chain_speak_stream(http_client, tone_wav: Path):
    if not os.environ.get("XI_API_KEY"):
        pytest.skip("XI_API_KEY not configured for chain speak")

    with tone_wav.open("rb") as handle:
        files = {"audio_file": ("tone.wav", handle, "audio/wav")}
        resp = http_client.post(
            "/speak",
            files=files,
            stream=True,
            timeout=60,
        )

    if resp.status_code == 422:
        body = resp.json()
        if body.get("code") == "VOICE_REQUIRED":
            pytest.xfail("Voice configuration missing; VOICE_REQUIRED expected")
    assert resp.status_code == 200
    collected = b"".join(resp.iter_content(chunk_size=8192))
    assert collected
    resp.close()
