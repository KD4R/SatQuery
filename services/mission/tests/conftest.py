"""
Shared pytest fixtures for mission service tests.
"""
import pytest
from fastapi.testclient import TestClient
from services.mission.implementation import app


@pytest.fixture(scope="module")
def mission_client():
    with TestClient(app) as c:
        yield c
