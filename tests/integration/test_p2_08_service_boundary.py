"""
tests/integration/test_p2_08_service_boundary.py
Integration tests for P2-08 service boundary: temporal planning via execute endpoint.
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
def test_p2_08_service_boundary(client, auth_headers):
    """POST /api/v1/agent/execute handles temporal_window parameter."""
    payload = {
        "query": "Assess temporal flood progression along Brahmaputra",
        "mission_id": "msn-progression-001",
        "temporal_window": {
            "baseline_start": "2026-08-01T00:00:00Z",
            "crisis_start": "2026-09-01T00:00:00Z",
        },
    }
    resp = client.post("/api/v1/agent/execute", json=payload, headers=auth_headers)
    assert resp.status_code == 202, resp.json()
    job_id = resp.json()["job_id"]

    run_resp = client.get(f"/api/v1/agent/runs/{job_id}", headers=auth_headers)
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "COMPLETED"
