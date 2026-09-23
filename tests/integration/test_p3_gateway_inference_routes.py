"""The gateway must expose the inference routes, with the right roles (P3 ↔ P5).

Lives in tests/ rather than services/inference/tests/ because it imports the
gateway: .importlinter forbids one service module importing another, and a test
inside services.inference doing it would break that contract for a reason that has
nothing to do with the boundary it protects.

Without these routes the browser cannot reach the model at all: the console may
only call the gateway, and the gateway had no route to the inference service.

The roles are exercised, not read off the decorator. An earlier version of this
file asserted only that the three paths existed while its docstring claimed the
roles were checked -- true of the code, but not of the test, which would have
stayed green if every route had been opened to VIEWER.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from packages.auth.tests.conftest import make_token
from services.gateway.implementation import app

pytestmark = pytest.mark.integration

ORG = "org-p3-inference"
TRACE = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"

#: path, method, and the lowest role the gateway must accept.
#: ANALYST to run an analysis, VIEWER to read -- the same split the inference
#: service enforces on its own routes.
ROUTES = [
    ("POST", "/api/v1/inference/analyses", "analyst"),
    ("GET", "/api/v1/inference/models", "viewer"),
    ("GET", f"/api/v1/inference/analyses/{TRACE}/extent", "viewer"),
]


def _headers(role: str | None) -> dict[str, str]:
    # A distinct peer per request: the rate limiter keys on the direct peer and
    # every TestClient call would otherwise share one bucket.
    headers = {"X-Forwarded-For": f"10.0.0.{uuid.uuid4().int % 254 + 1}"}
    if role is not None:
        headers["Authorization"] = f"Bearer {make_token(roles=[role], org_id=ORG)}"
    return headers


@pytest.fixture(scope="module")
def gw():
    from services.gateway.middleware.rate_limit import RateLimitMiddleware

    with TestClient(app, raise_server_exceptions=False) as client:
        node = app.middleware_stack
        while node is not None and not isinstance(node, RateLimitMiddleware):
            node = getattr(node, "app", None)
        assert isinstance(node, RateLimitMiddleware), "rate limiter missing from gateway stack"
        node._max_requests = 10_000
        yield client


@pytest.mark.parametrize("method,path,_role", ROUTES)
def test_route_exists(gw, method: str, path: str, _role: str) -> None:
    """Not 404 -- the gateway knows the path at all."""
    response = gw.request(method, path, headers=_headers(None))
    assert response.status_code != 404, f"gateway does not proxy {method} {path}"


@pytest.mark.parametrize("method,path,_role", ROUTES)
def test_route_requires_authentication(gw, method: str, path: str, _role: str) -> None:
    response = gw.request(method, path, headers=_headers(None))
    assert response.status_code == 401


def test_running_an_analysis_is_refused_to_a_viewer(gw) -> None:
    """The one route that costs GPU time and writes artifacts is ANALYST+."""
    response = gw.post("/api/v1/inference/analyses", headers=_headers("viewer"), json={})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "method,path",
    [(m, p) for m, p, role in ROUTES if role == "viewer"],
)
def test_reading_is_allowed_to_a_viewer(gw, method: str, path: str) -> None:
    """Reading the registry or an extent must not need ANALYST.

    The downstream call is stubbed at the transport boundary because this asserts
    the gateway's own gate, not the inference service's behaviour -- but the stub
    returns a real 200, so a 403 here could only come from the role check.
    """
    downstream = httpx.Response(
        200,
        json={"models": [], "default": None},
        request=httpx.Request(method, f"http://inference{path}"),
    )
    with patch(
        "services.gateway.routers.proxy.InternalClient._request",
        new=AsyncMock(return_value=downstream),
    ):
        response = gw.request(method, path, headers=_headers("viewer"))
    assert response.status_code != 403, response.text
    assert response.status_code == 200, response.text
