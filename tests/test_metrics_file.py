from __future__ import annotations

import time

import pytest


def test_metrics_file_contains_recent_entries(http_client, metrics_path, tone_wav):
    with tone_wav.open("rb") as handle:
        files = {"audio_file": ("tone.wav", handle, "audio/wav")}
        resp = http_client.post("/stt", files=files, timeout=30)
    if resp.status_code == 429:
        pytest.skip("Rate limit triggered before metrics check")
    assert resp.status_code in {200, 401}
    time.sleep(0.5)
    assert metrics_path.exists()
    lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    recent = lines[-5:] if len(lines) > 5 else lines
    assert any("stt" in entry or "speak" in entry for entry in recent)
