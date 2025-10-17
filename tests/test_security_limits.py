from __future__ import annotations

import pytest

from tests.utils import HTTPClient


def test_security_requires_api_key_when_enabled(test_env, security_enabled, tone_wav):
    if not security_enabled:
        pytest.skip("Security disabled in test environment")

    client = HTTPClient(test_env["base_url"])  # type: ignore[arg-type]
    with tone_wav.open("rb") as handle:
        files = {"audio_file": ("tone.wav", handle, "audio/wav")}
        resp = client.post("/stt", files=files, timeout=10)
    assert resp.status_code == 401
    payload = resp.json()
    assert payload.get("code") == "UNAUTHORIZED"


def test_security_allows_with_api_key(http_client, security_enabled, tone_wav):
    if not security_enabled:
        pytest.skip("Security disabled in test environment")
    with tone_wav.open("rb") as handle:
        files = {"audio_file": ("tone.wav", handle, "audio/wav")}
        resp = http_client.post("/stt", files=files, timeout=30)
    assert resp.status_code in {200, 422}


def test_rate_limit_trigger(http_client):
    target = 500
    for _ in range(target):
        resp = http_client.get("/health", timeout=5)
        if resp.status_code == 429:
            assert resp.json().get("code") == "RATE_LIMIT"
            return
    pytest.skip("Rate limit not triggered; RATE_LIMIT_* may be high for current run")
