from __future__ import annotations

import os
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_ENABLE_ADMIN", "0") not in {"1", "true", "True"},
    reason="Admin tests disabled; set TEST_ENABLE_ADMIN=1 to enable",
)


def test_terms_admin_roundtrip(http_client):
    pytest.skip("Admin functionality disabled")
