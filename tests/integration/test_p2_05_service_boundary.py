"""
tests/integration/test_p2_05_service_boundary.py
Integration tests for P2-05 service boundary: tools schema endpoint.
"""

from typing import Any
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from services.agent.tests.helpers.test_tokens import make_test_token
from services.agent.app.api.implementation import app as agent_app
from services.agent.tools.base import BaseTool, ToolPermissionTier, ToolResult
from services.agent.tools.registry import get_tool_registry


class _DummyArgs(BaseModel):
    hazard_type: str = "flood"


class _SampleTool(BaseTool):
    name = "hazard_detector"
    version = "1.0.0"
    description = "Detects hazards in satellite imagery"
    permission_tier = ToolPermissionTier.READ
    args_schema = _DummyArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True, output="detected")


@pytest.fixture(scope="module")
def client():
    # Register tool to global registry
    get_tool_registry().register(_SampleTool())
    with TestClient(agent_app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers():
    token = make_test_token("user:analyst-1", "org-isro", roles=["analyst"])
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_p2_05_service_boundary(client, auth_headers):
    """GET /api/v1/agent/tools lists available tools with schemas and permission tiers."""
    resp = client.get("/api/v1/agent/tools", headers=auth_headers)
    assert resp.status_code == 200, resp.json()
    tools = resp.json()
    assert isinstance(tools, list)
    assert len(tools) >= 1
    hazard_tool = next((t for t in tools if t["name"] == "hazard_detector"), None)
    assert hazard_tool is not None
    assert hazard_tool["version"] == "1.0.0"
    assert hazard_tool["permission_tier"] == "read"
    assert "parameters" in hazard_tool
