"""
tests/integration/test_p2_11_service_boundary.py
Integration tests for P2-11 service boundary: confidence gate endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from packages.auth.testing import make_test_token
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
def test_p2_11_service_boundary(client, auth_headers):
    """POST /api/v1/agent/confidence returns confidence score and gate evaluation."""
    payload = {
        "sensor_type": "SAR",
        "cloud_cover": 0.0,
        "resolution_meters": 10.0,
        "evidence_nodes": [
            {
                "node_id": "inf-1",
                "node_type": "INFERENCE",
                "confidence": 0.94,
            }
        ],
    }
    resp = client.post("/api/v1/agent/confidence", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["passed_gate"] is True
    assert data["confidence_score"] >= 0.70
    assert data["action"] == "PROCEED"
