"""
packages/auth/tests/conftest.py — Shared fixtures for auth tests.

Uses HS256 with a deterministic test secret so tests never need a
real OIDC provider. The algorithm/secret are set via environment
variables BEFORE the config singleton is initialised.
"""

import time
from typing import Dict, List, Optional

import pytest
from jose import jwt

# ── Test constants ─────────────────────────────────────────────────────────────
TEST_SECRET = "test-secret-key-not-for-production-use-at-all"
TEST_ALGORITHM = "HS256"
TEST_AUDIENCE = "satquery-api"
TEST_ISSUER = "https://auth.satquery.test"
TEST_ORG_ID = "org-test-001"


def make_token(
    subject: str = "user-123",
    org_id: str = TEST_ORG_ID,
    roles: Optional[List[str]] = None,
    email: Optional[str] = "test@satquery.test",
    audience: str = TEST_AUDIENCE,
    issuer: str = TEST_ISSUER,
    expires_in: int = 3600,
    extra_claims: Optional[Dict] = None,
) -> str:
    """
    Factory: create a signed HS256 JWT for use in tests.
    Never use this in production code.
    """
    now = int(time.time())
    payload: Dict = {
        "sub": subject,
        "org_id": org_id,
        "email": email,
        "roles": roles or ["analyst"],
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + expires_in,
    }
    if extra_claims:
        payload.update(extra_claims)
    return str(jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM))


def make_expired_token(**kwargs) -> str:
    """Create a token that is already expired."""
    return make_token(expires_in=-60, **kwargs)


@pytest.fixture(autouse=True)
def configure_hs256_auth(monkeypatch):
    """
    Set AUTH_* env vars to HS256 mode and reset the settings singleton
    before every test. This ensures tests are always isolated from each
    other and from any real environment config.
    """
    monkeypatch.setenv("AUTH_ALGORITHM", TEST_ALGORITHM)
    monkeypatch.setenv("AUTH_SECRET_KEY", TEST_SECRET)
    monkeypatch.setenv("AUTH_AUDIENCE", TEST_AUDIENCE)
    monkeypatch.setenv("AUTH_ISSUER", TEST_ISSUER)
    monkeypatch.delenv("AUTH_JWKS_URL", raising=False)

    # Reset singleton so it re-reads the patched env vars.
    from packages.auth import config as auth_config

    auth_config.reset_auth_settings()

    yield

    # Teardown — reset again so the next test starts clean.
    auth_config.reset_auth_settings()
