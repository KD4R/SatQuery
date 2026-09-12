"""
tests/integration/test_p2_01_service_boundary.py
Integration tests for P2-01 service boundary.
"""

import pytest
from fastapi.testclient import TestClient

from services.agent.app.api.implementation import app as agent_app
from services.gateway.implementation import app as gateway_app
from services.mission.implementation import app as mission_app


@pytest.fixture(scope="module")
def agent_client():
    with TestClient(agent_app) as c:
        yield c


@pytest.fixture(scope="module")
def gateway_client():
    with TestClient(gateway_app) as c:
        yield c


@pytest.fixture(scope="module")
def mission_client():
    with TestClient(mission_app) as c:
        yield c


@pytest.mark.integration
def test_p2_01_service_boundary(agent_client, gateway_client, mission_client):
    """Agent service is independently reachable, healthy, and isolated."""
    resp = agent_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "agent"}

    gw_resp = gateway_client.get("/api/v1/health")
    ms_resp = mission_client.get("/api/v1/health")
    assert resp.json()["service"] != gw_resp.json()["service"]
    assert resp.json()["service"] != ms_resp.json()["service"]
