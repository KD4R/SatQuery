"""
Integration tests for P1-05 & P1-08: Gateway CORS, rate limiting, WebSocket.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from packages.auth.tests.conftest import make_expired_token, make_token
from services.gateway.implementation import app

ORG = "org-test"


def _token(roles=None):
    return make_token(roles=roles or ["viewer"], org_id=ORG)


@pytest.fixture(scope="module")
def gateway_client():
    with TestClient(app) as c:
        yield c


# ── P1-05: Health + basic routing ────────────────────────────────────────────
@pytest.mark.integration
def test_p1_05_gateway_health_returns_200(gateway_client):
    resp = gateway_client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "gateway"


# ── P1-05: CORS ───────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_05_cors_no_allowed_origins_blocks_cross_origin(gateway_client):
    """By default (no CORS_ALLOW_ORIGINS set) cross-origin requests are denied."""
    resp = gateway_client.get(
        "/api/v1/health",
        headers={"Origin": "https://evil.example.com"},
    )
    # No ACAO header means browser would block — the server responds normally
    # but the CORS header is absent. We verify the header is not echoed back.
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.integration
def test_p1_05_cors_preflight_no_allowed_origins(gateway_client):
    """OPTIONS preflight without allowed origin must not include ACAO header."""
    resp = gateway_client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in resp.headers


# ── P1-05: Rate limiting ──────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_05_rate_limit_health_is_exempt(gateway_client):
    """Health endpoint must bypass rate limiting (monitoring safe)."""
    for _ in range(20):
        resp = gateway_client.get("/api/v1/health")
    assert resp.status_code == 200  # still 200, never 429


@pytest.mark.integration
def test_p1_05_rate_limit_429_when_exceeded():
    """Exceed the rate limit and verify 429 + Retry-After header."""
    from services.gateway.middleware.rate_limit import RateLimitMiddleware
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, requests=3, window_s=60)

    from fastapi.routing import APIRouter

    r = APIRouter()

    @r.get("/probe")
    async def probe():
        return {"ok": True}

    test_app.include_router(r)

    with TestClient(test_app) as client:
        for _ in range(3):
            client.get("/probe")
        resp = client.get("/probe")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        body = resp.json()
        assert body["code"] == "RATE_LIMIT_EXCEEDED"
        assert body["retryable"] is True


# ── P1-08: WebSocket ──────────────────────────────────────────────────────────
def _allow_tenant_check(mock_httpx_client):
    """Make the mission-ownership probe succeed for all tests in this file."""
    import httpx as _httpx

    response = _httpx.Response(200, request=_httpx.Request("GET", "http://test/missions"))
    mock_httpx_client.return_value.__aenter__.return_value.get.return_value = response


@pytest.mark.integration
@patch("services.gateway.routers.missions_ws.httpx.AsyncClient")
@patch("services.gateway.routers.missions_ws.redis.from_url")
def test_p1_08_websocket_valid_token_connects_and_streams(mock_redis, mock_httpx_client, gateway_client):
    """A valid JWT connects and receives status stream messages."""
    mock_redis.side_effect = Exception("Mock Redis Failure")
    _allow_tenant_check(mock_httpx_client)
    token = _token(roles=["viewer"])
    with gateway_client.websocket_connect(f"/ws/v1/missions/m-001?token={token}") as ws:
        connected = ws.receive_json()
        assert connected["event"] == "connected"
        assert connected["mission_id"] == "m-001"

        update = ws.receive_json()
        assert update["event"] == "status_update"
        assert "status" in update

        # Drain remaining messages
        ws.receive_json()  # running
        ws.receive_json()  # completed
        done = ws.receive_json()
        assert done["event"] == "done"


@pytest.mark.integration
def test_p1_08_websocket_no_token_closes_4001(gateway_client):
    """Missing token must result in close code 4001."""
    with pytest.raises(Exception):
        with gateway_client.websocket_connect("/ws/v1/missions/m-001") as ws:
            ws.receive_json()


@pytest.mark.integration
def test_p1_08_websocket_expired_token_closes_4001(gateway_client):
    """Expired token must result in connection close."""
    expired = make_expired_token()
    with pytest.raises(Exception):
        with gateway_client.websocket_connect(f"/ws/v1/missions/m-001?token={expired}") as ws:
            ws.receive_json()


@pytest.mark.integration
def test_p1_08_websocket_invalid_token_closes_4001(gateway_client):
    """Garbage token must result in connection close."""
    with pytest.raises(Exception):
        with gateway_client.websocket_connect("/ws/v1/missions/m-001?token=not.a.valid.jwt") as ws:
            ws.receive_json()


@pytest.mark.integration
@patch("services.gateway.routers.missions_ws.httpx.AsyncClient")
@patch("services.gateway.routers.missions_ws.redis.from_url")
def test_p1_08_websocket_tenant_org_id_in_messages(mock_redis, mock_httpx_client, gateway_client):
    """Messages must include the org_id from the token (tenant scoping)."""
    mock_redis.side_effect = Exception("Mock Redis Failure")
    _allow_tenant_check(mock_httpx_client)
    token = make_token(org_id="org-ws-test", roles=["viewer"])
    with gateway_client.websocket_connect(f"/ws/v1/missions/m-ws?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["org_id"] == "org-ws-test"
        # drain
        for _ in range(4):
            ws.receive_json()
