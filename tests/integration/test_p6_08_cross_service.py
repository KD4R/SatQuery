"""
P6-08 — Cross-service integration test suite

Verifies that services can communicate correctly through their
versioned API boundaries. These tests validate contract conformance
between gateway, agent, mission, and geo services by spinning up
the actual Docker Compose environment and sending live HTTP requests.
"""

import httpx
import pytest

from infrastructure.docker.implementation import check_service_health


pytestmark = pytest.mark.integration


# -- Cross Service Integration Tests --


class TestTrueCrossServiceIntegration:
    """End-to-End multi-container integration tests."""

    def test_gateway_proxies_to_mission(self, docker_available, compose_env):
        """Gateway must proxy /api/v1/missions to the Mission service."""
        assert check_service_health("api"), "API Gateway must be healthy"
        assert check_service_health("mission"), "Mission service must be healthy"

        with httpx.Client(base_url="http://localhost:8000", timeout=10) as client:
            response = client.get("/api/v1/missions")
            # Proxied endpoint returns standard HTTP errors, not 503/502/404 from the proxy itself
            assert response.status_code in (
                200,
                401,
                403,
            ), f"Unexpected status: {response.status_code}"

    def test_gateway_proxies_to_agent(self, docker_available, compose_env):
        """Gateway must proxy /api/v1/agent/tools to the Agent service."""
        assert check_service_health("agent"), "Agent service must be healthy"

        with httpx.Client(base_url="http://localhost:8000", timeout=10) as client:
            response = client.get("/api/v1/agent/tools")
            assert response.status_code in (
                200,
                401,
                403,
            ), f"Unexpected status: {response.status_code}"


# -- Service Boundary --


class TestP608ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        """Service code must not import from test modules."""
        for svc_dir in ["services/agent/security", "services/agent/tools", "services/agent/nodes"]:
            from pathlib import Path

            p = Path(svc_dir)
            if not p.exists():
                continue
            for py_file in p.glob("*.py"):
                if py_file.name.startswith("test_"):
                    continue
                content = py_file.read_text(errors="ignore")
                assert "from tests" not in content, f"{py_file} imports from tests"
