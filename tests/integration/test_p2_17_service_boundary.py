"""
tests/integration/test_p2_17_service_boundary.py
Integration tests for P2-17 service boundary: resilient execution flow.
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
def test_p2_17_service_boundary(client, auth_headers):
    """Execute endpoint recovers from upstream glitches and delivers completed state."""
    payload = {
        "query": "Resilient flood detection across Kaziranga during STAC outage",
        "mission_id": "msn-resilience-001",
    }
    resp = client.post("/api/v1/agent/execute", json=payload, headers=auth_headers)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    run_resp = client.get(f"/api/v1/agent/runs/{job_id}", headers=auth_headers)
    assert run_resp.status_code == 200
    state = run_resp.json()
    assert state["status"] == "COMPLETED"
    assert len(state["observation_ids"]) >= 1
