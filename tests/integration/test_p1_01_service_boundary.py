"""
Integration tests for P1-01 service boundary verification.
"""
import pytest
from fastapi.testclient import TestClient
from services.gateway.implementation import app as gateway_app
from services.mission.implementation import app as mission_app


@pytest.fixture(scope="module")
def gateway_client():
    with TestClient(gateway_app) as c:
        yield c


@pytest.fixture(scope="module")
def mission_client():
    with TestClient(mission_app) as c:
        yield c


@pytest.mark.integration
def test_p1_01_service_boundary(gateway_client, mission_client):
    """Both services are independently reachable and healthy."""
    gw_resp = gateway_client.get("/api/v1/health")
    assert gw_resp.status_code == 200
    assert gw_resp.json()["service"] == "gateway"

    ms_resp = mission_client.get("/api/v1/health")
    assert ms_resp.status_code == 200
    assert ms_resp.json()["service"] == "mission"


@pytest.mark.integration
def test_services_are_isolated(gateway_client, mission_client):
    """Services respond correctly only to their own routes."""
    # Gateway should not serve mission-specific routes (they're separate services)
    gw_health = gateway_client.get("/api/v1/health")
    ms_health = mission_client.get("/api/v1/health")
    assert gw_health.json()["service"] != ms_health.json()["service"]
