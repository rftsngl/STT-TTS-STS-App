from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Generator, Optional

import pytest
import requests
import wave

from tests.utils import (
    HTTPClient,
    ensure_reports_dir,
    find_free_port,
    make_tone_wav,
    mask,
)


def _collect_env_overrides(port: int) -> Dict[str, str]:
    base_env = os.environ.copy()
    reports_dir = Path("reports/tests")
    ensure_reports_dir(reports_dir)
    metrics_path = reports_dir / "metrics.jl"

    overrides: Dict[str, str] = {
        "HOST": "127.0.0.1",
        "PORT": str(port),
        "LOG_METRICS": "1",
        "METRICS_JL_PATH": str(metrics_path.resolve()),
        "RATE_LIMIT_GLOBAL_RPM": base_env.get("RATE_LIMIT_GLOBAL_RPM", "600"),
        "RATE_LIMIT_IP_RPM": base_env.get("RATE_LIMIT_IP_RPM", "300"),
        "WS_IDLE_TIMEOUT_SEC": base_env.get("WS_IDLE_TIMEOUT_SEC", "10"),
        "WS_PING_INTERVAL_SEC": base_env.get("WS_PING_INTERVAL_SEC", "3"),
        "WS_PONG_TIMEOUT_SEC": base_env.get("WS_PONG_TIMEOUT_SEC", "2"),
        "ENABLE_HEARTBEAT": base_env.get("ENABLE_HEARTBEAT", "1"),
        "WS_INCOMING_MAX_QUEUE": base_env.get("WS_INCOMING_MAX_QUEUE", "64"),
        "WS_OUTGOING_MAX_QUEUE": base_env.get("WS_OUTGOING_MAX_QUEUE", "64"),
    }
    for key in ("ENABLE_SECURITY", "API_KEY"):
        if key in base_env:
            overrides[key] = base_env[key]
    return overrides


def _wait_for_server(base_url: str, timeout: float = 25.0) -> bool:
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            resp = requests.get(f"{base_url}/health", timeout=3)
            if resp.status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def test_env() -> Generator[Dict[str, object], None, None]:
    base_env = os.environ.copy()
    preferred_port = int(base_env.get("TEST_PORT", "8001") or "8001")
    port = find_free_port(preferred_port)
    overrides = _collect_env_overrides(port)
    env = base_env.copy()
    env.update(overrides)

    base_url = f"http://127.0.0.1:{port}"
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
    )

    try:
        if not _wait_for_server(base_url):
            raise RuntimeError("Server did not become ready in time")
        yield {
            "base_url": base_url,
            "env": env,
            "metrics_path": Path(env["METRICS_JL_PATH"]),
            "reports_dir": Path("reports/tests"),
            "security_enabled": env.get("ENABLE_SECURITY", "0") in {"1", "true", "True"},
            "api_key": env.get("API_KEY") or None,
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        # allow uvicorn to release port
        time.sleep(0.5)


@pytest.fixture(scope="session")
def base_url(test_env: Dict[str, object]) -> str:
    return str(test_env["base_url"])


@pytest.fixture(scope="session")
def api_key(test_env: Dict[str, object]) -> Optional[str]:
    return test_env.get("api_key")  # type: ignore[return-value]




@pytest.fixture(scope="session")
def reports_dir(test_env: Dict[str, object]) -> Path:
    return Path(test_env["reports_dir"])  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def metrics_path(test_env: Dict[str, object]) -> Path:
    metrics_path = Path(test_env["metrics_path"])  # type: ignore[arg-type]
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    return metrics_path


@pytest.fixture(scope="session")
def tone_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("audio") / "tone.wav"
    return make_tone_wav(path)


@pytest.fixture(scope="session")
def silence_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("audio") / "silence.wav"
    samples = int(16000 * 1.0)
    pcm = (b"\x00\x00") * samples
    with wave.open(str(path), "wb") as wf:  # type: ignore[name-defined]
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm)
    return path


@pytest.fixture(scope="session")
def http_client(base_url: str, api_key: Optional[str]) -> HTTPClient:
    return HTTPClient(base_url, api_key=api_key)


@pytest.fixture(scope="session")
def security_enabled(test_env: Dict[str, object]) -> bool:
    return bool(test_env["security_enabled"])


@pytest.fixture(scope="session")
def masked_api_key(api_key: Optional[str]) -> Optional[str]:
    return mask(api_key) if api_key else None


def pytest_configure(config: pytest.Config) -> None:
    reports_dir = Path("reports/tests")
    ensure_reports_dir(reports_dir)
