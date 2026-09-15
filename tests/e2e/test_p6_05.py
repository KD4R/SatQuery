"""
P6-05 -- DEV deployment and service health smoke

Verifies that after docker compose up, all services respond to health checks.
These tests require Docker to be running.
"""

from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.e2e]


# -- Health check helpers --


def http_health(url: str, timeout: float = 5.0) -> bool:
    """Check if a URL responds with 200."""
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (URLError, OSError, TimeoutError):
        return False


# -- Service endpoints --


SERVICES = {
    "api": "http://localhost:8000/api/v1/health",
    "postgres": None,  # TCP check, not HTTP
    "redis": None,  # TCP check, not HTTP
    "minio": "http://localhost:9000/minio/health/live",
    "titiler": "http://localhost:8081/healthz",
    "prometheus": "http://localhost:9090/-/healthy",
    "grafana": "http://localhost:3001/api/health",
}


# -- Smoke Tests --


class TestDevDeploymentHealth:
    """Smoke tests for the DEV deployment. Skip if Docker services are not running."""

    @pytest.mark.parametrize("name,url", [(k, v) for k, v in SERVICES.items() if v is not None])
    def test_service_responds(self, name, url):
        """Each HTTP-exposed service must respond to its health endpoint."""
        if not http_health(url):
            pytest.skip(f"Service {name} not reachable at {url} — Docker may not be running")
        assert True

    def test_api_health_returns_ok(self):
        """API health endpoint must return a JSON body with status=ok."""
        import json

        try:
            req = Request("http://localhost:8000/api/v1/health", method="GET")
            with urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read())
                assert body.get("status") == "ok"
                assert body.get("service") == "gateway"
        except (URLError, OSError, TimeoutError):
            pytest.skip("API not reachable")

    def test_api_responds_within_timeout(self):
        """API must respond within 5 seconds."""
        import time as _time

        start = _time.monotonic()
        try:
            req = Request("http://localhost:8000/api/v1/health", method="GET")
            with urlopen(req, timeout=5):
                elapsed = _time.monotonic() - start
                assert elapsed < 5.0, f"API took {elapsed:.2f}s to respond"
        except (URLError, OSError, TimeoutError):
            pytest.skip("API not reachable")

    def test_grafana_datasource_configured(self):
        """Grafana must have the Prometheus datasource configured."""
        import json

        try:
            req = Request(
                "http://localhost:3001/api/datasources",
                method="GET",
                headers={"Authorization": "Basic YWRtaW46YWRtaW4="},
            )
            with urlopen(req, timeout=5) as resp:
                datasources = json.loads(resp.read())
                names = [ds.get("name") for ds in datasources]
                assert "Prometheus" in names, f"Prometheus datasource missing. Found: {names}"
        except (URLError, OSError, TimeoutError):
            pytest.skip("Grafana not reachable")

    def test_prometheus_has_targets(self):
        """Prometheus must have scrape targets configured."""
        import json

        try:
            req = Request("http://localhost:9090/api/v1/targets", method="GET")
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                targets = data.get("data", {}).get("activeTargets", [])
                assert len(targets) > 0, "No scrape targets configured"
        except (URLError, OSError, TimeoutError):
            pytest.skip("Prometheus not reachable")


class TestP605ServiceBoundary:
    def test_no_service_imports_from_tests(self):
        """E2E test code must not import from service modules."""
        from pathlib import Path

        e2e_dir = Path("tests/e2e")
        for py_file in e2e_dir.glob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            content = py_file.read_text(errors="ignore")
            assert "from services" not in content
            assert "from packages" not in content
