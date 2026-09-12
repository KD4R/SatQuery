"""
tests/integration/test_p2_14_service_boundary.py
Integration tests for P2-14 service boundary: synthesized output in runs.
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
def test_p2_14_service_boundary(client, auth_headers):
    """Execute endpoint produces evidence-grounded synthesized output."""
    payload = {
        "query": "Explain inundation damage and sensor selection for Assam flood",
        "mission_id": "msn-synth-integration-001",
    }
    resp = client.post("/api/v1/agent/execute", json=payload, headers=auth_headers)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    run_resp = client.get(f"/api/v1/agent/runs/{job_id}", headers=auth_headers)
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert data["status"] == "COMPLETED"
    assert data["synthesized_output"] is not None
    assert data["synthesized_output"]["inundation_area_sqkm"] > 0
