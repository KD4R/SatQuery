"""
tests/integration/test_p2_14_service_boundary.py
Integration tests for P2-14 service boundary: synthesized output in runs.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.agent.tests.helpers.test_tokens import make_test_token
from services.agent.app.api.implementation import app as agent_app


@pytest.fixture(scope="module")
def client():
    with TestClient(agent_app) as c:
        yield c


@pytest.fixture(autouse=True)
def mock_orchestrator_deps():
    with (
        patch("services.agent.graph.orchestrator.get_tool_executor") as mock_executor,
        patch("packages.shared.client.InternalClient.post", new_callable=AsyncMock) as mock_post,
    ):

        # Mock STAC search tool
        mock_tool_res = MagicMock()
        mock_tool_res.success = True
        mock_tool_res.output = [
            {"asset_id": "S1A_IW_GRDH_1SDV_TEST_1", "href": "s3://test/scene.tif"}
        ]
        mock_executor.return_value.execute_tool.return_value = mock_tool_res

        # Mock Inference response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "completed",
            "measurements": [{"name": "inundation_area_sqkm", "value": 14250.0}],
            "degraded_from": "baseline",
        }
        mock_post.return_value = mock_resp

        yield


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
