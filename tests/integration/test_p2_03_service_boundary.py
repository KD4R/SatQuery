"""
tests/integration/test_p2_03_service_boundary.py
Integration tests for P2-03 service boundary: planning endpoint.
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
def test_p2_03_service_boundary(client, auth_headers):
    """Calling /api/v1/agent/plan yields structured steps, mission intent, and sensors."""
    payload = {
        "query": "Assess Assam flood extent and affected buildings",
        "mission_id": "msn-assam-001",
        "aoi": {
            "type": "Polygon",
            "coordinates": [
                [
                    [92.5, 26.1],
                    [93.0, 26.1],
                    [93.0, 26.5],
                    [92.5, 26.5],
                    [92.5, 26.1],
                ]
            ],
        },
    }
    resp = client.post("/api/v1/agent/plan", json=payload, headers=auth_headers)
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["mission_id"] == "msn-assam-001"
    assert data["intent"]["disaster_type"] == "flood"
    assert "S1_SAR" in data["selected_sensors"]
    assert len(data["plan_steps"]) >= 5
    assert any(s["name"] == "confidence_gate" for s in data["plan_steps"])
