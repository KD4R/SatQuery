"""
Shared pytest fixtures for gateway service tests.
"""

import pytest
from fastapi.testclient import TestClient
from services.gateway.implementation import app


@pytest.fixture(scope="module")
def gateway_client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_gateway_rate_limit_bucket():
    """Keep module-shared TestClient cases independent.

    The production limiter is intentionally process-local for the single-process
    test/dev profile. Tests must not inherit request timestamps from another
    gateway test module, otherwise a legitimate 404 can become a 429.
    """
    node = app.middleware_stack
    while node is not None:
        if node.__class__.__name__ == "RateLimitMiddleware":
            node._store.clear()
            break
        node = getattr(node, "app", None)
    yield
