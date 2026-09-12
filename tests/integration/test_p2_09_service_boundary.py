"""
tests/integration/test_p2_09_service_boundary.py
Integration tests for P2-09 service boundary: sensor decision endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from conftest import make_test_token
from services.agent.app.api.implementation import app as agent_app


@pytest.fixture(scope="module")
def client():
    with TestClient(agent_app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    token = make_test_token("user:analyst-1", "org-isro", roles=["analyst"])
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_p2_09_service_boundary(client, auth_headers):
    """POST /api/v1/agent/sensor-decision returns valid arbitration decision."""
    payload = {
        "hazard_type": "flood",
        "cloud_cover_percentage": 55.0,
        "is_night": False,
        "priority": "balanced",
    }
    resp = client.post("/api/v1/agent/sensor-decision", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["primary_sensor"] == "SAR"
    assert data["arbitration_score"] >= 0.90
    assert "microwave" in data["rationale"]
