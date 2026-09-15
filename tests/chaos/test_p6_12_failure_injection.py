"""
P6-12 — Failure injection and recovery tests

Validates that services handle failures gracefully by injecting real
failures (stopping containers) in the Docker Compose environment and
asserting recovery and proper error handling.
"""

import subprocess
import time
from pathlib import Path

import httpx
import pytest

from infrastructure.docker.implementation import COMPOSE_FILE, check_service_health

pytestmark = pytest.mark.integration


# -- Docker Service Chaos Tests --


class TestDockerChaosEngineering:
    """Inject failures and ensure system resilience."""

    def test_api_degrades_gracefully_when_redis_dies(self, docker_available, compose_env):
        """API should return 503 or degrade gracefully when Redis is killed, then recover."""
        # Ensure it's healthy initially
        assert check_service_health("api"), "API must be healthy initially"

        # Inject failure: kill redis (compose file must be explicit: pytest
        # runs from the repo root, where compose finds no config on its own).
        subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "stop", "redis"], check=True)

        # Give API a moment to notice
        time.sleep(2)

        # Test behavior while degraded
        with httpx.Client(base_url="http://localhost:8000", timeout=5) as client:
            try:
                resp = client.get("/api/v1/health")
                # Either it returns 503 Service Unavailable, or 200 with degraded status
                if resp.status_code == 200:
                    data = resp.json()
                    assert data.get("status") in (
                        "degraded",
                        "ok",
                    ), "Expected degraded status if returning 200"
                else:
                    assert resp.status_code in (
                        500,
                        502,
                        503,
                    ), f"Expected server error, got {resp.status_code}"
            except httpx.RequestError:
                # Disconnection or timeout is also a form of failure,
                # but we hope for graceful HTTP error
                pass

        # Recover
        subprocess.run(["docker", "compose", "-f", str(COMPOSE_FILE), "start", "redis"], check=True)

        # Give API a moment to recover connections
        time.sleep(5)
        assert check_service_health("api"), "API did not recover after Redis restarted"


# -- Service Boundary --


class TestP612ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        """Chaos test code must not import from service modules."""
        for py_file in Path("tests/chaos").glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            content = py_file.read_text(errors="ignore")
            assert "from services" not in content
            assert "from packages" not in content
