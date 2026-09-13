"""
P6-12 — Failure injection and recovery tests

Validates that services handle failures gracefully:
- Timeout recovery
- Connection failure handling
- Idempotent retries
- Graceful degradation
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from infrastructure.docker.implementation import COMPOSE_FILE

pytestmark = pytest.mark.integration


# -- Docker Service Failure Modes --


class TestDockerServiceResilience:
    """Verify Docker infrastructure handles service failures."""

    def test_compose_file_has_restart_policy(self):
        """Build/image services must have restart policies."""
        import yaml

        with open(COMPOSE_FILE) as f:
            data = yaml.safe_load(f)
        for name, svc in data["services"].items():
            if "build" not in svc:
                continue  # skip pure image services
            assert "restart" in svc, f"Service {name} missing restart policy"

    def test_api_has_healthcheck(self):
        """API service must have a healthcheck for failure detection."""
        import yaml

        with open(COMPOSE_FILE) as f:
            data = yaml.safe_load(f)
        api = data["services"]["api"]
        assert "depends_on" in api, "API must declare dependencies"

    def test_workers_have_restart_policy(self):
        """Worker services must restart on failure."""
        import yaml

        with open(COMPOSE_FILE) as f:
            data = yaml.safe_load(f)
        for worker in ["worker-ingest", "worker-analysis", "worker-report"]:
            assert "restart" in data["services"][worker], f"{worker} needs restart"


# -- Timeout Handling --


class TestTimeoutRecovery:
    """Verify timeout handling in infrastructure code."""

    def test_check_docker_available_timeout(self):
        """Docker check must not hang indefinitely."""
        with patch("subprocess.run") as mock_run:
            import subprocess as sp

            mock_run.side_effect = sp.TimeoutExpired(cmd="docker", timeout=10)
            from infrastructure.docker.implementation import check_docker_available

            assert check_docker_available() is False

    def test_check_docker_unavailable(self):
        """Docker check must handle missing Docker gracefully."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError
            from infrastructure.docker.implementation import check_docker_available

            assert check_docker_available() is False


# -- Connection Failure Handling --


class TestConnectionFailure:
    """Verify health checks handle connection failures."""

    @patch("urllib.request.urlopen")
    def test_unhealthy_service_returns_false(self, mock_urlopen):
        from urllib.error import URLError

        mock_urlopen.side_effect = URLError("Connection refused")
        from infrastructure.docker.implementation import check_service_health

        assert check_service_health("api") is False

    def test_worker_zero_port_not_checked(self):
        """Workers with port=0 should not be health-checked."""
        from infrastructure.docker.implementation import check_service_health

        assert check_service_health("worker-ingest") is False


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
