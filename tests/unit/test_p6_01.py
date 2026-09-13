"""
P6-01 — Docker Compose local integration environment

Unit tests for infrastructure/docker/implementation.py
"""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.docker.implementation import (
    COMPOSE_DIR,
    COMPOSE_FILE,
    ENV_EXAMPLE,
    PROJECT_ROOT,
    EnvironmentConfig,
    ServiceConfig,
    check_docker_available,
    ensure_env_file,
    get_compose_services,
)

pytestmark = pytest.mark.unit


# ── ServiceConfig ─────────────────────────────────────────────────────────────


class TestServiceConfig:
    def test_service_config_url_construction(self):
        svc = ServiceConfig(name="api", port=8000)
        assert svc.url == "http://localhost:8000"

    def test_service_config_with_health_endpoint(self):
        svc = ServiceConfig(name="api", port=8000, health_endpoint="/health")
        assert svc.url == "http://localhost:8000"
        assert svc.health_endpoint == "/health"

    def test_service_config_immutable(self):
        svc = ServiceConfig(name="api", port=8000)
        with pytest.raises(AttributeError):
            svc.port = 9000  # type: ignore[misc]

    def test_service_config_zero_port_worker(self):
        svc = ServiceConfig(name="worker-ingest", port=0)
        assert svc.port == 0
        assert svc.url == "http://localhost:0"


# ── EnvironmentConfig ─────────────────────────────────────────────────────────


class TestEnvironmentConfig:
    def test_default_services_present(self):
        config = EnvironmentConfig()
        assert "api" in config.services
        assert "postgres" in config.services
        assert "redis" in config.services
        assert "minio" in config.services
        assert "titiler" in config.services
        assert "prometheus" in config.services
        assert "grafana" in config.services
        assert "otel-collector" in config.services
        assert "worker-ingest" in config.services
        assert "worker-analysis" in config.services
        assert "worker-report" in config.services

    def test_api_service_config(self):
        config = EnvironmentConfig()
        api = config.services["api"]
        assert api.port == 8000
        assert api.health_endpoint == "/api/v1/health"

    def test_web_service_config(self):
        config = EnvironmentConfig()
        web = config.services["web"]
        assert web.port == 3000
        assert "api" in web.depends_on

    def test_api_depends_on_infrastructure(self):
        config = EnvironmentConfig()
        api = config.services["api"]
        assert "postgres" in api.depends_on
        assert "redis" in api.depends_on
        assert "minio" in api.depends_on


# ── Path Constants ────────────────────────────────────────────────────────────


class TestPathConstants:
    def test_compose_dir_exists(self):
        assert COMPOSE_DIR.exists()
        assert COMPOSE_DIR.is_dir()

    def test_compose_file_exists(self):
        assert COMPOSE_FILE.exists()
        assert COMPOSE_FILE.name == "docker-compose.yml"

    def test_env_example_exists(self):
        assert ENV_EXAMPLE.exists()
        assert ENV_EXAMPLE.name == ".env.example"

    def test_project_root_is_correct(self):
        assert PROJECT_ROOT.name == "SatQuery" or (PROJECT_ROOT / "pyproject.toml").exists()


# ── ensure_env_file ───────────────────────────────────────────────────────────


class TestEnsureEnvFile:
    def test_creates_env_from_example(self, tmp_path):
        """Test that .env is created from .env.example when it doesn't exist."""
        env_path = tmp_path / ".env"
        example_path = tmp_path / ".env.example"
        example_path.write_text("POSTGRES_PASSWORD=test\n")

        with (
            patch("infrastructure.docker.implementation.ENV_FILE", env_path),
            patch("infrastructure.docker.implementation.ENV_EXAMPLE", example_path),
        ):
            result = ensure_env_file()
            assert result == env_path
            assert env_path.exists()
            assert "POSTGRES_PASSWORD=test" in env_path.read_text()

    def test_does_not_overwrite_existing_env(self, tmp_path):
        """Test that existing .env is not overwritten."""
        env_path = tmp_path / ".env"
        env_path.write_text("EXISTING_VAR=value\n")

        with patch("infrastructure.docker.implementation.ENV_FILE", env_path):
            result = ensure_env_file()
            assert result == env_path
            assert "EXISTING_VAR=value" in env_path.read_text()


# ── check_docker_available ────────────────────────────────────────────────────


class TestCheckDockerAvailable:
    @patch("subprocess.run")
    def test_docker_available(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="Docker Compose version v2.x.x")
        assert check_docker_available() is True

    @patch("subprocess.run")
    def test_docker_not_available(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        assert check_docker_available() is False

    @patch("subprocess.run")
    def test_docker_timeout(self, mock_run):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=10)
        assert check_docker_available() is False


# ── get_compose_services ──────────────────────────────────────────────────────


class TestGetComposeServices:
    @patch("subprocess.run")
    def test_returns_services_list(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="api\nweb\npostgres\nredis\nminio\n",
        )
        services = get_compose_services()
        assert "api" in services
        assert "postgres" in services
        assert len(services) == 5

    @patch("subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        services = get_compose_services()
        assert services == []


# ── Schema Compatibility ──────────────────────────────────────────────────────


class TestP601SchemaCompatibility:
    """Verify that the P6-01 implementation conforms to expected schemas."""

    def test_compose_file_is_valid_yaml(self):
        """docker-compose.yml must be valid YAML."""
        import yaml

        with open(COMPOSE_FILE) as f:
            data = yaml.safe_load(f)
        assert "services" in data
        assert isinstance(data["services"], dict)

    def test_all_services_have_images_or_build(self):
        """Every service must have either an image or build directive."""
        import yaml

        with open(COMPOSE_FILE) as f:
            data = yaml.safe_load(f)
        for name, svc in data["services"].items():
            assert "image" in svc or "build" in svc, f"Service '{name}' has no image or build"

    def test_env_example_has_required_vars(self):
        """Environment example must define core variables."""
        content = ENV_EXAMPLE.read_text()
        required_vars = [
            "POSTGRES_PASSWORD",
            "REDIS_PORT",
            "MINIO_ROOT_USER",
            "API_PORT",
            "WEB_PORT",
        ]
        for var in required_vars:
            assert var in content, f"Missing required variable: {var}"


# ── Service Boundary ──────────────────────────────────────────────────────────


class TestP601ServiceBoundary:
    """Verify P6-01 respects module boundaries."""

    def test_no_service_imports_from_tests(self):
        """Infrastructure code must not import from test modules."""
        impl_path = COMPOSE_DIR / "implementation.py"
        content = impl_path.read_text()
        # Check there are no test imports in the implementation
        assert "from tests" not in content
        assert "import tests" not in content

    def test_no_secrets_in_compose(self):
        """docker-compose.yml must not contain hardcoded secrets."""
        content = COMPOSE_FILE.read_text().lower()
        # These patterns should not appear as literal passwords
        assert "password=supersecret" not in content
        assert "api_key=sk-" not in content
        assert "secret_key=abc123" not in content
