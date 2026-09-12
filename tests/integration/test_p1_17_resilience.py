"""
Integration tests for P1-17: Internal Client Resilience.
"""

import asyncio
import httpx
import pytest

from packages.shared.client import InternalClient, InternalClientError, CircuitBreakerOpenError
from packages.auth.models import AuthContext


@pytest.fixture
def mock_auth_context() -> AuthContext:
    return AuthContext(
        subject="user123",
        organisation_id="tenant_x",
        roles=[],
        trace_id=None,
    )


@pytest.mark.asyncio
async def test_p1_17_client_retries_on_timeout(mock_auth_context):
    """Verify the client automatically retries if the network times out."""
    client = InternalClient(base_url="http://test-service", caller_service="gateway", scopes=[])

    attempts = 0

    async def mock_send(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            # Simulate a timeout by raising httpx.TimeoutException
            raise httpx.TimeoutException("Mock timeout")
        # On 3rd attempt, succeed
        return httpx.Response(200, json={"status": "ok"})

    client.client = httpx.AsyncClient(
        base_url="http://test-service", transport=httpx.MockTransport(mock_send)
    )

    # This should succeed after 3 attempts due to @retry
    resp = await client.get("/api/v1/test", auth_context=mock_auth_context)
    assert resp.status_code == 200
    assert attempts == 3


@pytest.mark.asyncio
async def test_p1_17_circuit_breaker_trips_on_500s(mock_auth_context):
    """Verify that consecutive 500 errors trip the circuit breaker."""
    client = InternalClient(base_url="http://test-service", caller_service="gateway", scopes=[])
    # Lower threshold for testing
    client.circuit_breaker.failure_threshold = 2

    calls = 0

    async def mock_send(request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"code": "SERVER_ERROR", "message": "Down"})

    client.client = httpx.AsyncClient(
        base_url="http://test-service", transport=httpx.MockTransport(mock_send)
    )

    # 1. First failure
    with pytest.raises(InternalClientError) as exc_info:
        await client.get("/api/v1/test", auth_context=mock_auth_context)
    assert exc_info.value.status_code == 500

    # 2. Second failure -> trips circuit breaker to OPEN
    with pytest.raises(InternalClientError):
        await client.get("/api/v1/test", auth_context=mock_auth_context)

    # 3. Third request -> fails immediately with CircuitBreakerOpenError (no network call)
    with pytest.raises(CircuitBreakerOpenError):
        await client.get("/api/v1/test", auth_context=mock_auth_context)

    # The actual network transport was only hit 2 times, the 3rd was short-circuited
    assert calls == 2


@pytest.mark.asyncio
async def test_p1_17_circuit_breaker_recovers(mock_auth_context):
    """Verify circuit breaker transitions from OPEN -> HALF_OPEN -> CLOSED."""
    client = InternalClient(base_url="http://test-service", caller_service="gateway", scopes=[])

    # Set threshold to 1 and recovery to a tiny value to test transitions
    client.circuit_breaker.failure_threshold = 1
    client.circuit_breaker.recovery_timeout = 0.1

    is_down = True

    async def mock_send(request: httpx.Request):
        if is_down:
            return httpx.Response(500, json={"code": "SERVER_ERROR", "message": "Down"})
        return httpx.Response(200, json={"status": "ok"})

    client.client = httpx.AsyncClient(
        base_url="http://test-service", transport=httpx.MockTransport(mock_send)
    )

    # 1. Trigger failure -> Trips to OPEN
    with pytest.raises(InternalClientError):
        await client.get("/api/v1/test", auth_context=mock_auth_context)

    assert client.circuit_breaker.state == "OPEN"

    # 2. Wait for recovery timeout to pass
    await asyncio.sleep(0.2)

    # 3. Service recovers. The next request is HALF_OPEN and succeeds, transitioning to CLOSED
    is_down = False
    resp = await client.get("/api/v1/test", auth_context=mock_auth_context)

    assert resp.status_code == 200
    assert client.circuit_breaker.state == "CLOSED"
