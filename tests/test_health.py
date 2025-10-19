from __future__ import annotations


def test_health(http_client):
    resp = http_client.get("/health", timeout=5)
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, dict)
    assert "status" in payload
    # Status can be "healthy" or "degraded" depending on API key configuration
    assert payload.get("status") in ["healthy", "degraded"]
    # Ensure elevenlabs status is present
    assert "elevenlabs" in payload
    assert "status" in payload["elevenlabs"]
