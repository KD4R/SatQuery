"""
tests/integration/test_p2_04_service_boundary.py
Integration tests for P2-04 service boundary: execute endpoint and run polling.
"""

import pytest
from fastapi.testclient import TestClient

from services.agent.tests.helpers.test_tokens import make_test_token
from services.agent.app.api.implementation import app as agent_app


@pytest.fixture(scope="module")
def client():
    with TestClient(agent_app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    token = make_test_token("user:analyst-1", "org-isro", roles=["analyst"])
    return {"Authorization": f"Bearer {token}", "X-Trace-Id": "tr-execute-001"}


@pytest.mark.integration
def test_p2_04_service_boundary(client, auth_headers):
    """POST /api/v1/agent/execute returns 202 Accepted, and run status can be retrieved."""
    payload = {
        "query": "Delineate water extent across Cachar district",
        "mission_id": "msn-cachar-001",
    }
    resp = client.post("/api/v1/agent/execute", json=payload, headers=auth_headers)
    assert resp.status_code == 202, resp.json()
    data = resp.json()
    assert data["status"] == "ACCEPTED"
    job_id = data["job_id"]
    assert job_id.startswith("job_")
    assert resp.headers.get("X-Job-Id") == job_id

    # Poll run status
    run_resp = client.get(f"/api/v1/agent/runs/{job_id}", headers=auth_headers)
    assert run_resp.status_code == 200, run_resp.json()
    run_data = run_resp.json()
    assert run_data["job_id"] == job_id
    assert run_data["status"] == "COMPLETED"
    assert run_data["synthesized_output"]["inundation_area_sqkm"] > 0
