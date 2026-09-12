"""
tests/integration/test_p2_07_service_boundary.py
Integration tests for P2-07 service boundary: STAC search & asset selector tools registered.
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
def test_p2_07_service_boundary(client, auth_headers):
    """GET /api/v1/agent/tools lists stac_search and asset_selector tools."""
    resp = client.get("/api/v1/agent/tools", headers=auth_headers)
    assert resp.status_code == 200, resp.json()
    tools = resp.json()
    tool_names = [t["name"] for t in tools]
    assert "stac_search" in tool_names
    assert "asset_selector" in tool_names

    stac_tool = next(t for t in tools if t["name"] == "stac_search")
    assert "bbox" in stac_tool["parameters"]["properties"]
    assert "sensors" in stac_tool["parameters"]["properties"]
