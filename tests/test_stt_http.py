from __future__ import annotations

from pathlib import Path

import pytest


def test_stt_small_audio(http_client, tone_wav: Path):
    with tone_wav.open("rb") as handle:
        files = {"audio_file": ("tone.wav", handle, "audio/wav")}
        resp = http_client.post("/stt", files=files, timeout=30)
    if resp.status_code == 429:
        pytest.skip("Rate limit reached before STT test")
    assert resp.status_code in {200, 401}
    if resp.status_code == 200:
        payload = resp.json()
        assert isinstance(payload, dict)
        assert "segments" in payload
        assert "text" in payload


@pytest.mark.parametrize("size_mb", [1])
def test_stt_payload_too_large(http_client, tmp_path, size_mb):
    oversize_path = tmp_path / "oversize.bin"
    oversize_path.write_bytes(b"\x00" * (size_mb * 1024 * 1024 + 1024))
    with oversize_path.open("rb") as handle:
        files = {"audio_file": ("oversize.bin", handle, "application/octet-stream")}
        resp = http_client.post("/stt", files=files, timeout=30)
    if resp.status_code == 429:
        pytest.skip("Rate limit reached before oversize check")
    assert resp.status_code in {413, 422, 401}
    if resp.status_code == 413:
        body = resp.json()
        assert body.get("code") == "PAYLOAD_TOO_LARGE"
