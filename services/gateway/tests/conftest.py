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
