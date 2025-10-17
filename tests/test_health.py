from __future__ import annotations


def test_health(http_client):
    resp = http_client.get("/health", timeout=5)
    assert resp.status_code == 200
    payload = resp.json()
    assert isinstance(payload, dict)
    assert "status" in payload
    assert payload.get("status") == "ok"
