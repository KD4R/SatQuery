"""
tests/integration/test_p2_12_service_boundary.py
Integration tests for P2-12 service boundary: multi-sensor disagreement integration.
"""

import pytest
from fastapi.testclient import TestClient

from conftest import make_test_token
from evidence.disagreement import analyze_sensor_disagreement
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
def test_p2_12_service_boundary(client, auth_headers):
    """Sensor disagreement integrates into the evidence analysis flow."""
    report = analyze_sensor_disagreement(
        sar_area_sqkm=142.5,
        optical_area_sqkm=138.0,
        intersection_sqkm=130.0,
    )
    assert report.iou_score > 0.85

    # Run execute flow which performs multi-sensor evidence building
    resp = client.post(
        "/api/v1/agent/execute",
        json={"query": "Perform multi-sensor flood validation in Assam"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    run_resp = client.get(f"/api/v1/agent/runs/{job_id}", headers=auth_headers)
    assert run_resp.status_code == 200
    assert run_resp.json()["status"] == "COMPLETED"
