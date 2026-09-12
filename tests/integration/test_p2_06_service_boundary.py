"""
tests/integration/test_p2_06_service_boundary.py
Integration tests for P2-06 service boundary: RBAC permission gating.
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
def viewer_headers():
    token = make_test_token("user:viewer-1", "org-isro", roles=["viewer"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def analyst_headers():
    token = make_test_token("user:analyst-1", "org-isro", roles=["analyst"])
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
def test_p2_06_service_boundary(client, viewer_headers, analyst_headers):
    """Viewer token cannot execute plan generation (HTTP 403), while analyst succeeds."""
    payload = {"query": "Assess Kaziranga flood"}

    # Viewer request rejected with 403
    v_resp = client.post("/api/v1/agent/plan", json=payload, headers=viewer_headers)
    assert v_resp.status_code == 403
    assert v_resp.json()["code"] == "INSUFFICIENT_PERMISSIONS"

    # Analyst request permitted with 200
    a_resp = client.post("/api/v1/agent/plan", json=payload, headers=analyst_headers)
    assert a_resp.status_code == 200
