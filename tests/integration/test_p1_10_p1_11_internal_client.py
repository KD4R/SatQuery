"""
Integration tests for P1-10 and P1-11: Shared Internal Client & S2S Identity
"""

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from packages.auth.dependencies import require_scope
from packages.auth.jwt import decode_and_verify, generate_s2s_token
from packages.auth.models import AuthContext
from packages.shared.client import InternalClient, InternalClientError


@pytest.fixture
def mock_auth_context() -> AuthContext:
    return AuthContext(
        subject="user123",
        organisation_id="tenant_x",
        roles=[],
        email="test@satquery.com",
        trace_id="test_trace_123",
    )


@pytest.mark.unit
def test_p1_11_generate_and_verify_s2s_token():
    """Verify generate_s2s_token creates a valid HS256 token that decode_and_verify accepts."""
    token = generate_s2s_token(
        caller_service="gateway", org_id="tenant_1", scopes=["mission:internal"]
    )

    # decode_and_verify should accept it since it uses HS256
    payload = decode_and_verify(token)
    assert payload["sub"] == "service:gateway"
    assert payload["org_id"] == "tenant_1"
    assert "system" in payload["roles"]
    assert "mission:internal" in payload["scopes"]


@pytest.mark.asyncio
async def test_p1_10_internal_client_injects_s2s_token(mock_auth_context):
    """Verify that InternalClient makes requests with a valid injected S2S token."""
    # We will mock the httpx client behavior to inspect the request
    client = InternalClient(
        base_url="http://test-service", caller_service="gateway", scopes=["test:scope"]
    )

    # Simple transport interceptor
    request_headers = {}

    async def mock_send(request: httpx.Request):
        nonlocal request_headers
        request_headers = request.headers
        return httpx.Response(200, json={"status": "ok"})

    client.client = httpx.AsyncClient(
        base_url="http://test-service", transport=httpx.MockTransport(mock_send)
    )

    resp = await client.get("/api/v1/test", auth_context=mock_auth_context)

    assert resp.status_code == 200
    assert "authorization" in request_headers

    auth_header = request_headers["authorization"]
    assert auth_header.startswith("Bearer ")
    token = auth_header.split(" ")[1]

    # Verify the injected token is valid and carries the correct context
    payload = decode_and_verify(token)
    assert payload["org_id"] == mock_auth_context.organisation_id
    assert "test:scope" in payload["scopes"]
    assert payload["sub"] == "service:gateway"


@pytest.mark.asyncio
async def test_p1_10_internal_client_maps_errors(mock_auth_context):
    """Verify that 4xx/5xx responses are caught and mapped to InternalClientError."""
    client = InternalClient(
        base_url="http://test-service", caller_service="gateway", scopes=["test:scope"]
    )

    # Simulate a downstream error returning our canonical ErrorResponse schema
    error_payload = {
        "code": "DOWNSTREAM_FAIL",
        "message": "The downstream service failed.",
        "retryable": True,
    }

    async def mock_send(request: httpx.Request):
        return httpx.Response(400, json=error_payload)

    client.client = httpx.AsyncClient(
        base_url="http://test-service", transport=httpx.MockTransport(mock_send)
    )

    with pytest.raises(InternalClientError) as exc_info:
        await client.get("/api/v1/fail", auth_context=mock_auth_context)

    assert exc_info.value.status_code == 400
    assert exc_info.value.error.code == "DOWNSTREAM_FAIL"
    assert exc_info.value.error.message == "The downstream service failed."


@pytest.mark.integration
def test_p1_11_require_scope_dependency():
    """Verify that FastAPI routes can be gated by JWT scopes."""
    app = FastAPI()
    router = APIRouter()

    @router.get("/internal-only", dependencies=[Depends(require_scope("admin:internal"))])
    def internal_route():
        return {"access": "granted"}

    app.include_router(router)
    client = TestClient(app)

    # 1. Access with a token that lacks the scope should fail (403)
    bad_token = generate_s2s_token("gateway", "tenant_1", scopes=["wrong:scope"])
    resp = client.get("/internal-only", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "INSUFFICIENT_SCOPES"

    # 2. Access with a token that has the scope should succeed
    good_token = generate_s2s_token("gateway", "tenant_1", scopes=["admin:internal"])
    resp2 = client.get("/internal-only", headers={"Authorization": f"Bearer {good_token}"})
    assert resp2.status_code == 200
    assert resp2.json()["access"] == "granted"
