"""P1-03 / A02: a shared-secret verifier must not start in a production environment."""

import pytest

from packages.auth.config import AuthSettings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("AUTH_JWKS_URL", "AUTH_SECRET_KEY", "ENVIRONMENT"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.unit
@pytest.mark.parametrize("environment", ["production", "PROD", "staging"])
def test_hs256_is_refused_in_production_like_environments(monkeypatch, environment):
    monkeypatch.setenv("AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_SECRET_KEY", "x" * 48)
    monkeypatch.setenv("ENVIRONMENT", environment)
    with pytest.raises(ValueError, match="not permitted"):
        AuthSettings()


@pytest.mark.unit
def test_hs256_still_works_for_local_development(monkeypatch):
    monkeypatch.setenv("AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("AUTH_SECRET_KEY", "dev-secret")
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert AuthSettings().algorithm == "HS256"


@pytest.mark.unit
def test_rs256_with_https_jwks_is_accepted_in_production(monkeypatch):
    monkeypatch.setenv("AUTH_ALGORITHM", "RS256")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://idp.example.org/.well-known/jwks.json")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert AuthSettings().algorithm == "RS256"
