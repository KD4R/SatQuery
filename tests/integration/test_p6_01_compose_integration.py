"""
P6-01 — Docker Compose local integration environment

Integration tests — verify the Docker Compose environment works end-to-end.
These tests require Docker to be running. Skip if Docker is unavailable.
"""

import subprocess
import time

import pytest

from infrastructure.docker.implementation import (
    COMPOSE_FILE,
    check_docker_available,
    check_service_health,
    get_service_status,
    start_environment,
    stop_environment,
)

pytestmark = pytest.mark.integration

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def docker_available():
    """Skip all integration tests if Docker is not available."""
    if not check_docker_available():
        pytest.skip("Docker is not available — skipping integration tests")
    return True


@pytest.fixture(scope="module")
def compose_env(docker_available):
    """Start and stop the Docker Compose environment for the test module."""
    # Start with build
    result = start_environment(build=True)
    if result.returncode != 0:
        pytest.fail(f"Failed to start Docker Compose: {result.stderr}")

    # Wait for services to become healthy
    time.sleep(10)

    yield

    # Teardown
    stop_environment()


# ── Integration Tests ─────────────────────────────────────────────────────────


class TestDockerComposeEnvironment:
    """Integration tests for the Docker Compose environment."""

    def test_compose_file_parses(self, docker_available):
        """docker-compose.yml must parse without errors."""
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--quiet"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Compose config validation failed: {result.stderr}"

    def test_all_services_defined(self, docker_available):
        """All expected services must be defined in compose."""
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--services"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        services = [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
        expected = {"api", "postgres", "redis", "minio", "titiler", "web"}
        assert expected.issubset(set(services)), f"Missing services: {expected - set(services)}"

    def test_compose_up_and_down(self, docker_available):
        """Verify compose up and down work without errors."""
        result = start_environment(detach=True, services=["postgres", "redis"])
        assert result.returncode == 0, f"Up failed: {result.stderr}"

        time.sleep(5)

        # Check status — get_service_status() keys by compose service name
        statuses = get_service_status()
        assert statuses.get("postgres") == "running"

        # Stop
        result = stop_environment()
        assert result.returncode == 0, f"Down failed: {result.stderr}"

    def test_postgres_health(self, compose_env):
        """PostgreSQL must be healthy and accepting connections."""
        assert check_service_health("postgres")

    def test_redis_health(self, compose_env):
        """Redis must be healthy and responding to ping."""
        assert check_service_health("redis")

    def test_minio_health(self, compose_env):
        """MinIO must be healthy and the console must be accessible."""
        assert check_service_health("minio")

    def test_api_health(self, compose_env):
        """API Gateway must respond to health check."""
        assert check_service_health("api")

    def test_titiler_health(self, compose_env):
        """TiTiler must be healthy and serving tiles."""
        assert check_service_health("titiler")

    def test_grafana_health(self, compose_env):
        """Grafana must be accessible."""
        assert check_service_health("grafana")

    def test_network_isolation(self, compose_env):
        """Services must be on the satquery network."""
        result = subprocess.run(
            ["docker", "network", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        networks = result.stdout
        assert "satquery" in networks

    def test_volumes_persist(self, compose_env):
        """Named volumes must exist for data persistence."""
        result = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        volumes = result.stdout
        assert "postgres_data" in volumes or "satquery_postgres_data" in volumes
