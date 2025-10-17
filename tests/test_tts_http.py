from __future__ import annotations

import os

import pytest


def test_tts_stream(http_client, api_key):
    xi_key = os.environ.get("XI_API_KEY") or os.environ.get("xi_api_key")
    if not xi_key:
        pytest.skip("XI_API_KEY not configured for TTS")

    resp = http_client.post(
        "/tts",
        data={"text": "Probe test."},
        stream=True,
        timeout=60,
    )
    if resp.status_code == 422:
        body = resp.json()
        if any(code in body.get("detail", "") or body.get("code") for code in ("VOICE_REQUIRED", "VOICE_ALIAS")):
            pytest.xfail("Voice configuration missing; VOICE_REQUIRED expected")
    assert resp.status_code == 200
    content = b"".join(list(resp.iter_content(chunk_size=8192)))
    assert content
    assert content[:3] in (b"ID3", b"RIFF")
    resp.close()
