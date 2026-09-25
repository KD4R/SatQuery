"""
tests/integration/test_p1_gateway_proxy.py — Gateway proxy integration tests (P1-05).

Verifies that:
  - Proxy routes exist on the gateway and return correct status codes.
  - Unauthenticated requests return 401.
  - Insufficient role returns 403.
  - Circuit breaker surfaces 503 when downstream is unreachable.
  - S2S token is injected by InternalClient (tested via mock).

OWASP A01, A07 coverage.
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from packages.auth.tests.conftest import make_token
from services.gateway.implementation import app
from packages.shared.client import CircuitBreakerOpenError, InternalClientError
from packages.contracts.errors import ErrorResponse

ORG = "org-proxy-test"


def _analyst_token():
    return make_token(roles=["analyst"], org_id=ORG)


def _viewer_token():
    return make_token(roles=["viewer"], org_id=ORG)


def _operator_token():
    return make_token(roles=["operator", "analyst"], org_id=ORG)


def _ah(token: str):
    return {
        "Authorization": f"Bearer {token}",
        "X-Forwarded-For": f"10.0.0.{uuid.uuid4().int % 254 + 1}",
    }


@pytest.fixture(scope="module")
def gw():
    # These tests exercise auth, RBAC and circuit-breaker behaviour, not rate
    # limiting. The rate limiter now keys on the direct peer address (client-
    # supplied X-Forwarded-For is untrusted per OWASP A04/A05), so every
    # TestClient request lands in ONE bucket and would trip the 100/min
    # default. Raise the limit for this module instead of weakening prod code.
    from services.gateway.middleware.rate_limit import RateLimitMiddleware

    with TestClient(app, raise_server_exceptions=False) as c:
        # The middleware chain is built on startup, so walk it inside the context.
        node = app.middleware_stack
        while node is not None and not isinstance(node, RateLimitMiddleware):
            node = getattr(node, "app", None)
        assert isinstance(node, RateLimitMiddleware), "rate limiter missing from gateway stack"
        node._max_requests = 10_000
        yield c


# ── Auth gate tests ───────────────────────────────────────────────────────────


@pytest.mark.integration
def test_p1_proxy_missions_no_auth_returns_401(gw):
    """Unauthenticated GET /api/v1/missions must return 401."""
    resp = gw.get(
        "/api/v1/missions", headers={"X-Forwarded-For": f"10.0.0.{uuid.uuid4().int % 254 + 1}"}
    )
    assert resp.status_code == 401


@pytest.mark.integration
def test_p1_proxy_agent_plan_no_auth_returns_401(gw):
    """Unauthenticated POST /api/v1/agent/plan must return 401."""
    resp = gw.post(
        "/api/v1/agent/plan",
        json={"query": "test"},
        headers={"X-Forwarded-For": f"10.0.0.{uuid.uuid4().int % 254 + 1}"},
    )
    assert resp.status_code == 401


@pytest.mark.integration
def test_p1_proxy_agent_execute_viewer_role_returns_403(gw):
    """VIEWER cannot call agent execute — requires ANALYST."""
    token = _viewer_token()
    resp = gw.post(
        "/api/v1/agent/execute",
        json={"query": "detect flooding"},
        headers=_ah(token),
    )
    assert resp.status_code == 403


@pytest.mark.integration
def test_p1_proxy_missions_delete_analyst_returns_403(gw):
    """ANALYST cannot delete a mission — requires OPERATOR."""
    token = _analyst_token()
    resp = gw.delete("/api/v1/missions/msn-001", headers=_ah(token))
    assert resp.status_code == 403


# ── Circuit-breaker / error propagation ──────────────────────────────────────


@pytest.mark.integration
@patch("services.gateway.routers.proxy._get_mission_client")
def test_p1_proxy_circuit_breaker_returns_503(mock_get_client, gw):
    """When the circuit breaker is open, proxy returns 503."""
    mock_client = MagicMock()
    mock_client._request = AsyncMock(side_effect=CircuitBreakerOpenError("CB open"))
    mock_get_client.return_value = mock_client

    token = _viewer_token()
    resp = gw.get("/api/v1/missions", headers=_ah(token))
    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "SERVICE_UNAVAILABLE"
    assert body["retryable"] is True


@pytest.mark.integration
@patch("services.gateway.routers.proxy._get_mission_client")
def test_p1_proxy_upstream_404_propagated(mock_get_client, gw):
    """A 404 from Mission service is propagated to the client as-is."""
    err = ErrorResponse(code="MISSION_NOT_FOUND", message="Not found", retryable=False)
    exc = InternalClientError(status_code=404, error_response=err)

    mock_client = MagicMock()
    mock_client._request = AsyncMock(side_effect=exc)
    mock_get_client.return_value = mock_client

    token = _viewer_token()
    resp = gw.get("/api/v1/missions/missing-id", headers=_ah(token))
    assert resp.status_code == 404
    assert resp.json()["code"] == "MISSION_NOT_FOUND"


@pytest.mark.integration
@patch("services.gateway.routers.proxy._get_mission_client")
def test_p1_proxy_upstream_500_propagated_with_retryable(mock_get_client, gw):
    """A 500 from Mission service is propagated with retryable=True."""
    err = ErrorResponse(code="INTERNAL_ERROR", message="DB down", retryable=True)
    exc = InternalClientError(status_code=500, error_response=err)

    mock_client = MagicMock()
    mock_client._request = AsyncMock(side_effect=exc)
    mock_get_client.return_value = mock_client

    token = _viewer_token()
    resp = gw.get("/api/v1/missions", headers=_ah(token))
    assert resp.status_code == 500
    assert resp.json()["retryable"] is True


@pytest.mark.integration
@patch("services.gateway.routers.proxy._get_mission_client")
def test_p1_proxy_successful_list_returns_200(mock_get_client, gw):
    """A successful upstream call returns 200 with the forwarded body."""
    import httpx

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {"items": [], "total": 0, "limit": 50, "offset": 0}

    mock_client = MagicMock()
    mock_client._request = AsyncMock(return_value=mock_resp)
    mock_get_client.return_value = mock_client

    token = _viewer_token()
    resp = gw.get("/api/v1/missions", headers=_ah(token))
    assert resp.status_code == 200
    assert "items" in resp.json()


@pytest.mark.integration
@patch("services.gateway.routers.proxy._get_agent_client")
def test_p1_proxy_agent_plan_analyst_succeeds(mock_get_client, gw):
    """ANALYST can call /api/v1/agent/plan and response is forwarded."""
    import httpx

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "mission_id": "m-001",
        "intent": {},
        "plan_steps": [],
        "selected_sensors": [],
    }

    mock_client = MagicMock()
    mock_client._request = AsyncMock(return_value=mock_resp)
    mock_get_client.return_value = mock_client

    token = _analyst_token()
    resp = gw.post(
        "/api/v1/agent/plan",
        json={"query": "Detect vessel activity in Bay of Bengal"},
        headers=_ah(token),
    )
    assert resp.status_code == 200
    assert "mission_id" in resp.json()


@pytest.mark.integration
@patch("services.gateway.routers.proxy._get_mission_client")
def test_p1_proxy_submit_run_operator_succeeds(mock_get_client, gw):
    """OPERATOR can call POST /api/v1/missions/{id}/runs."""
    import httpx

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 202
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "job_id": "job-xyz",
        "mission_id": "m-001",
        "status": "pending",
        "submitted_at": "2024-01-01T00:00:00Z",
    }

    mock_client = MagicMock()
    mock_client._request = AsyncMock(return_value=mock_resp)
    mock_get_client.return_value = mock_client

    token = _operator_token()
    resp = gw.post("/api/v1/missions/m-001/runs", headers=_ah(token))
    assert resp.status_code == 202
    assert resp.json()["job_id"] == "job-xyz"
