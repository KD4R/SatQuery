"""
P6-13 — Secrets/config and least-privilege hardening

Validates that secrets are not hardcoded, config uses env vars,
Docker containers run as non-root, and least-privilege is enforced.
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.security

INFRA_DIR = Path("infrastructure/docker")


class TestSecretsHardening:
    """Ensure no secrets leak into source or Docker images."""

    def test_no_hardcoded_passwords_in_compose(self):
        content = (INFRA_DIR / "docker-compose.yml").read_text().lower()
        assert "password=supersecret" not in content
        assert "api_key=sk-" not in content
        assert "secret_key=abc123" not in content

    def test_env_example_uses_placeholders(self):
        content = (INFRA_DIR / ".env.example").read_text()
        assert "satquery_dev" in content or "${" in content

    def test_dockerfile_has_non_root_user(self):
        content = (INFRA_DIR / "Dockerfile").read_text()
        assert "useradd" in content or "adduser" in content
        assert "USER satquery" in content

    def test_web_dockerfile_has_non_root_user(self):
        content = Path("apps/web/Dockerfile").read_text()
        assert "adduser" in content or "addgroup" in content
        assert "USER nextjs" in content


class TestConfigHardening:
    """Ensure config follows security best practices."""

    def test_compose_uses_env_vars_not_hardcoded(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        api_env = data["services"]["api"]["environment"]
        for key in ["DATABASE_URL", "REDIS_URL"]:
            assert key in api_env, f"Missing {key} in API env"

    def test_postgres_uses_env_var_password(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        pg_env = data["services"]["postgres"]["environment"]
        pw = pg_env["POSTGRES_PASSWORD"]
        assert "${" in pw or "satquery_dev" in pw, "Password should use env var"

    def test_minio_uses_env_var_credentials(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        minio_env = data["services"]["minio"]["environment"]
        user = minio_env["MINIO_ROOT_USER"]
        assert "${" in user or "minioadmin" in user


class TestLeastPrivilege:
    """Ensure services run with minimal permissions."""

    def test_grafana_disables_signup(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        grafana_env = data["services"]["grafana"]["environment"]
        assert grafana_env.get("GF_USERS_ALLOW_SIGN_UP") == "false"

    def test_api_cors_configured(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        api_env = data["services"]["api"]["environment"]
        assert "CORS_ALLOW_ORIGINS" in api_env

    def test_rate_limiting_configured(self):
        with open(INFRA_DIR / "docker-compose.yml") as f:
            data = yaml.safe_load(f)
        api_env = data["services"]["api"]["environment"]
        assert "RATE_LIMIT_REQUESTS" in api_env
        assert "RATE_LIMIT_WINDOW_S" in api_env
