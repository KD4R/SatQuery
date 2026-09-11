"""
Unit tests for the Mission service skeleton (P1-01).
"""
import pytest


@pytest.mark.unit
def test_monorepo_and_service_skeletons_valid(mission_client):
    """Mission health endpoint returns 200 with correct body."""
    response = mission_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "mission"


@pytest.mark.unit
def test_monorepo_and_service_skeletons_invalid_input(mission_client):
    """Unknown routes return 404."""
    response = mission_client.get("/api/v1/non_existent_route")
    assert response.status_code == 404


@pytest.mark.unit
def test_mission_health_response_schema(mission_client):
    """Mission health endpoint response has expected keys."""
    response = mission_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "service"}


@pytest.mark.unit
def test_mission_health_content_type(mission_client):
    """Mission health endpoint returns JSON content type."""
    response = mission_client.get("/api/v1/health")
    assert "application/json" in response.headers["content-type"]
