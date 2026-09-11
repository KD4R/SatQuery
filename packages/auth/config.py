"""
packages/auth/config.py — Auth configuration loaded from environment variables.

OWASP notes:
  - Secrets are never logged.
  - Algorithm is allowlisted (RS256 in prod, HS256 in test only).
  - Audience and issuer validation are mandatory in production.
"""

import os
from typing import Optional


class AuthSettings:
    """
    Auth configuration resolved from environment variables.

    Environment variables:
        AUTH_ALGORITHM        RS256 (default, OIDC) | HS256 (test only)
        AUTH_SECRET_KEY       Required when ALGORITHM=HS256 (test/dev only)
        AUTH_JWKS_URL         Required when ALGORITHM=RS256; OIDC JWKS endpoint
        AUTH_AUDIENCE         Expected 'aud' claim value
        AUTH_ISSUER           Expected 'iss' claim value
        AUTH_REQUIRE_HTTPS    1 (default) — refuse non-https JWKS URLs
    """

    def __init__(self) -> None:
        self.algorithm: str = os.getenv("AUTH_ALGORITHM", "RS256")
        self.secret_key: Optional[str] = os.getenv("AUTH_SECRET_KEY")
        self.jwks_url: Optional[str] = os.getenv("AUTH_JWKS_URL")
        self.audience: Optional[str] = os.getenv("AUTH_AUDIENCE")
        self.issuer: Optional[str] = os.getenv("AUTH_ISSUER")
        self.require_https: bool = os.getenv("AUTH_REQUIRE_HTTPS", "1") != "0"

        self._validate()

    def _validate(self) -> None:
        allowed = {"RS256", "HS256"}
        if self.algorithm not in allowed:
            raise ValueError(f"AUTH_ALGORITHM must be one of {allowed}, got '{self.algorithm}'")
        if self.algorithm == "RS256" and not self.jwks_url:
            raise ValueError("AUTH_JWKS_URL is required when AUTH_ALGORITHM=RS256")
        if self.algorithm == "HS256" and not self.secret_key:
            raise ValueError("AUTH_SECRET_KEY is required when AUTH_ALGORITHM=HS256")
        if (
            self.algorithm == "RS256"
            and self.jwks_url
            and self.require_https
            and not self.jwks_url.startswith("https://")
        ):
            raise ValueError(
                "AUTH_JWKS_URL must use HTTPS in production "
                "(set AUTH_REQUIRE_HTTPS=0 only in local dev)"
            )


# Singleton — instantiated lazily so tests can patch env before import.
_settings: Optional[AuthSettings] = None


def get_auth_settings() -> AuthSettings:
    """Return (and lazily initialise) the global AuthSettings singleton."""
    global _settings
    if _settings is None:
        _settings = AuthSettings()
    return _settings


def reset_auth_settings() -> None:
    """Reset the singleton — for use in tests only."""
    global _settings
    _settings = None
