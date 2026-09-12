"""
tests/integration/test_p2_13_service_boundary.py
Integration tests for P2-13 service boundary: autonomous acquisition during execution.
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
def test_p2_13_service_boundary(client, auth_headers):
    """Execution endpoint autonomously acquires observations and achieves confidence."""
    payload = {
        "query": "Autonomous flood monitoring in Assam cloud cover",
        "mission_id": "msn-loop-integration-001",
    }
    resp = client.post("/api/v1/agent/execute", json=payload, headers=auth_headers)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    run_resp = client.get(f"/api/v1/agent/runs/{job_id}", headers=auth_headers)
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert data["status"] == "COMPLETED"
    assert data["confidence_score"] >= 0.70
    assert len(data["observation_ids"]) >= 2
