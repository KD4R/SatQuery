"""
Integration tests for P1-12: Idempotency.
"""

import pytest
from fastapi.testclient import TestClient

from services.mission.implementation import app
from packages.shared.middleware.idempotency import _IDEMPOTENCY_STORE


@pytest.fixture(autouse=True)
def clear_idempotency_store():
    _IDEMPOTENCY_STORE.clear()
    yield
    _IDEMPOTENCY_STORE.clear()


@pytest.mark.integration
def test_p1_12_idempotency_key_caches_response():
    """
    Verify that making two requests with the same Idempotency-Key
    returns the exact same cached response without creating duplicate state.
    """
    client = TestClient(app)

    # Generate a valid token so the endpoint doesn't fail auth
    from packages.auth.jwt import generate_s2s_token

    token = generate_s2s_token("test-user", "tenant_1", scopes=[])

    # 1. First request creates a mission
    payload = {"name": "Idempotent Mission", "description": "Test", "aoi_ids": ["aoi1"]}
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "idemp-key-123"}

    resp1 = client.post("/api/v1/missions", json=payload, headers=headers)
    assert resp1.status_code == 201
    mission_id = resp1.json()["id"]

    # 2. Second request with the exact same key
    resp2 = client.post("/api/v1/missions", json=payload, headers=headers)
    assert resp2.status_code == 201
    assert resp2.json()["id"] == mission_id  # Exact same mission ID, no new creation

    # 3. Request with a DIFFERENT key creates a NEW mission
    headers["Idempotency-Key"] = "idemp-key-456"
    resp3 = client.post("/api/v1/missions", json=payload, headers=headers)
    assert resp3.status_code == 201
    assert resp3.json()["id"] != mission_id  # Different mission ID
