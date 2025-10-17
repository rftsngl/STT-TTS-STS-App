from __future__ import annotations

import json
import os
import time

import pytest

from tests.utils import pcm20ms_blocks, ws_connect


pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_ENABLE_RESILIENCE", "0") not in {"1", "true", "True"},
    reason="Resilience tests disabled; set TEST_ENABLE_RESILIENCE=1 to enable",
)


def _ws_url(base_url: str, path: str) -> str:
    return base_url.replace("http", "ws", 1) + path


@pytest.mark.timeout(60)
def test_ws_idle_timeout(test_env, tone_wav, api_key):
    if ws_connect is None:  # pragma: no cover
        pytest.skip("websocket-client is required")
    ws = ws_connect(_ws_url(test_env["base_url"], "/ws/speak"), api_key=api_key, timeout=10)  # type: ignore[arg-type]
    try:
        ws.send(
            json.dumps(
                {
                    "type": "start",
                    "language": "tr",
                    "sample_rate": 16000,
                    "voice_alias": "",
                }
            )
        )
        frames = list(pcm20ms_blocks(tone_wav, block_ms=20))[:5]
        for frame in frames:
            ws.send_binary(frame)
        time.sleep(20)
        ws.settimeout(5)
        error_seen = False
        while True:
            try:
                message = ws.recv()
            except Exception:
                break
            if isinstance(message, str):
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "error" and payload.get("code") == "WS_IDLE_TIMEOUT":
                    error_seen = True
                    break
    finally:
        ws.close()
    assert error_seen, "Expected WS_IDLE_TIMEOUT error"


@pytest.mark.timeout(60)
def test_ws_queue_overflow(test_env, tone_wav, api_key):
    if ws_connect is None:  # pragma: no cover
        pytest.skip("websocket-client is required")
    ws = ws_connect(_ws_url(test_env["base_url"], "/ws/speak"), api_key=api_key, timeout=10)  # type: ignore[arg-type]
    try:
        ws.send(
            json.dumps(
                {
                    "type": "start",
                    "language": "tr",
                    "sample_rate": 16000,
                    "voice_alias": "",
                }
            )
        )
        frames = list(pcm20ms_blocks(tone_wav, block_ms=20)) * 40
        for frame in frames:
            ws.send_binary(frame)
        ws.settimeout(5)
        overflow = False
        while True:
            try:
                message = ws.recv()
            except Exception:
                break
            if isinstance(message, str):
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "error" and payload.get("code") == "WS_QUEUE_OVERFLOW":
                    overflow = True
                    break
    finally:
        ws.close()
    assert overflow, "Expected WS_QUEUE_OVERFLOW error"
