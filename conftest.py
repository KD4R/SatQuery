"""
Root conftest.py — applies to ALL tests across the entire repo.

Responsibilities:
  1. PYTHONPATH fix so `services.*` and `packages.*` imports resolve.
  2. Session-scoped HS256 auth env vars — set via os.environ (not monkeypatch)
     so they are in place BEFORE any module-level code runs (e.g., module-scoped
     TestClient fixtures). This is the correct pattern for module/session-scoped
     fixtures that depend on env vars.
"""

import os
import sys

# ── 1. PYTHONPATH ----------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

# ── 2. Auth env vars — set at import time so module-scoped fixtures see them --
# These configure the auth layer to use HS256 for ALL tests.
# In production the container sets AUTH_ALGORITHM=RS256 + AUTH_JWKS_URL.
# We use a no-op default so existing env overrides are respected in local dev.
_TEST_AUTH_DEFAULTS = {
    "AUTH_ALGORITHM": "HS256",
    "AUTH_SECRET_KEY": "test-secret-key-not-for-production-use-at-all",
    "AUTH_AUDIENCE": "satquery-api",
    "AUTH_ISSUER": "https://auth.satquery.test",
}

for _key, _val in _TEST_AUTH_DEFAULTS.items():
    # Only set if not already set — allows local dev to override via .env
    os.environ.setdefault(_key, _val)

# Force HS256 in CI — never let RS256 be active without a real JWKS URL.
# If someone sets AUTH_ALGORITHM=RS256 without AUTH_JWKS_URL it would break;
# in tests we always want HS256.
os.environ["AUTH_ALGORITHM"] = "HS256"

try:
    from packages.auth import config as _auth_config

    _auth_config.reset_auth_settings()
except ImportError:
    pass  # packages/auth not yet on path — safe to ignore at collection time


from packages.auth.testing import make_test_token  # noqa: E402

__all__ = ["make_test_token"]
