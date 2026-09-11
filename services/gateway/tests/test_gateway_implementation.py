"""
Unit tests for the Gateway service skeleton (P1-01).
"""
import pytest


@pytest.mark.unit
def test_monorepo_and_service_skeletons_valid(gateway_client):
    """Gateway health endpoint returns 200 with correct body."""
    response = gateway_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "gateway"


@pytest.mark.unit
def test_monorepo_and_service_skeletons_invalid_input(gateway_client):
    """Unknown routes return 404."""
    response = gateway_client.get("/api/v1/non_existent_route")
    assert response.status_code == 404


@pytest.mark.unit
def test_gateway_health_response_schema(gateway_client):
    """Gateway health endpoint response has expected keys."""
    response = gateway_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"status", "service"}


@pytest.mark.unit
def test_gateway_health_content_type(gateway_client):
    """Gateway health endpoint returns JSON content type."""
    response = gateway_client.get("/api/v1/health")
    assert "application/json" in response.headers["content-type"]
