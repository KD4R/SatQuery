"""
tests/integration/test_p2_10_service_boundary.py
Integration tests for P2-10 service boundary: evidence graph integrated into runs.
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
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_p2_10_service_boundary(client, auth_headers):
    """Execution yields an EvidenceGraph in the completed MissionState."""
    payload = {
        "query": "Assess flood extent in Brahmaputra basin",
        "mission_id": "msn-evidence-001",
    }
    resp = client.post("/api/v1/agent/execute", json=payload, headers=auth_headers)
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    run_resp = client.get(f"/api/v1/agent/runs/{job_id}", headers=auth_headers)
    assert run_resp.status_code == 200
    state = run_resp.json()
    assert state["status"] == "COMPLETED"
    assert state["evidence_graph"] is not None
    graph = state["evidence_graph"]
    assert "nodes" in graph
    assert "edges" in graph
    assert any(n["node_type"] == "OBSERVATION" for n in graph["nodes"].values())
    assert any(n["node_type"] == "METRIC" for n in graph["nodes"].values())
