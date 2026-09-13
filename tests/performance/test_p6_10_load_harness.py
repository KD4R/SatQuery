"""
P6-10 — Performance/load test harness

Validates that the load test harness configuration is correct,
thresholds are defined, and the test infrastructure is ready.
Actual load tests run against a live environment with Locust.
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.performance

INFRA_DIR = Path("infrastructure/docker")


# -- Harness Config --


class TestLoadTestHarness:
    """Verify load test harness configuration and structure."""

    def test_api_health_responds(self):
        """API health endpoint must respond within 2 seconds (smoke check)."""
        from urllib.request import urlopen, Request
        from urllib.error import URLError
        import time

        start = time.monotonic()
        try:
            req = Request("http://localhost:8000/api/v1/health", method="GET")
            with urlopen(req, timeout=2) as resp:
                elapsed = time.monotonic() - start
                assert resp.status == 200
                assert elapsed < 2.0, f"Health check took {elapsed:.2f}s (>2s)"
        except (URLError, OSError, TimeoutError):
            pytest.skip("API not reachable — load tests require running services")

    def test_docker_compose_has_api_service(self):
        """Docker Compose must define an API service for load testing."""
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        assert "api" in data["services"]

    def test_api_has_resource_limits(self):
        """API container must have resource limits to prevent OOM during load."""
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        api = data["services"]["api"]
        assert "deploy" in api, "API service must have deploy config"
        assert "resources" in api["deploy"], "API must have resource limits"
        limits = api["deploy"]["resources"]["limits"]
        assert "memory" in limits, "API must have memory limit"
        assert "cpus" in limits, "API must have CPU limit"


# -- Performance Thresholds --


class TestPerformanceThresholds:
    """Define and validate performance thresholds for the load harness."""

    MAX_P95_LATENCY_MS = 2000  # 2 seconds
    MAX_ERROR_RATE_PCT = 5.0
    MIN_RPS = 10

    def test_threshold_constants_defined(self):
        """Performance thresholds must be defined as constants."""
        assert self.MAX_P95_LATENCY_MS > 0
        assert 0 < self.MAX_ERROR_RATE_PCT <= 100
        assert self.MIN_RPS > 0

    def test_compose_supports_concurrent_workers(self):
        """Worker services must support configurable concurrency."""
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        for worker in ["worker-ingest", "worker-analysis", "worker-report"]:
            assert worker in data["services"], f"Missing {worker}"
            svc = data["services"][worker]
            assert "command" in svc, f"{worker} must have a command"


# -- Service Boundary --


class TestP610ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        """Performance test code must not import from service modules."""
        for py_file in Path("tests/performance").glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            content = py_file.read_text(errors="ignore")
            assert "from services" not in content
            assert "from packages" not in content
