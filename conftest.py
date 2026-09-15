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

# ── 1b. Module aliases for hyphenated service directories -------------------
# Python cannot import `services.eo_data` from a folder named `eo-data` (hyphen).
# This MetaPathFinder transparently maps the canonical underscore name to the
# physical hyphenated directory for all submodule imports.
import importlib
import importlib.abc
import importlib.machinery
import importlib.util

_repo_root = os.path.abspath(os.path.dirname(__file__))

# Map: canonical Python module prefix → physical directory path
_HYPHEN_ALIASES: dict = {
    "services.eo_data": os.path.join(_repo_root, "services", "eo-data"),
    "services.geo": os.path.join(_repo_root, "services", "geo"),
}


class _HyphenServiceFinder(importlib.abc.MetaPathFinder):
    """Resolves `services.eo_data.*` → `services/eo-data/*` at import time."""

    def find_spec(self, fullname, path, target=None):
        for alias_prefix, physical_dir in _HYPHEN_ALIASES.items():
            if fullname == alias_prefix:
                # Package itself
                init_path = os.path.join(physical_dir, "__init__.py")
                if os.path.exists(init_path):
                    spec = importlib.util.spec_from_file_location(
                        fullname,
                        init_path,
                        submodule_search_locations=[physical_dir],
                    )
                else:
                    # Treat as namespace package if no __init__.py
                    spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
                    spec.submodule_search_locations = [physical_dir]
                return spec
            if fullname.startswith(alias_prefix + "."):
                subpath = fullname[len(alias_prefix) + 1 :].replace(".", os.sep)
                # Try as a module file first, then as a package directory
                for candidate in [
                    os.path.join(physical_dir, subpath + ".py"),
                    os.path.join(physical_dir, subpath, "__init__.py"),
                ]:
                    if os.path.exists(candidate):
                        search_locs = (
                            [os.path.join(physical_dir, subpath)]
                            if candidate.endswith("__init__.py")
                            else None
                        )
                        spec = importlib.util.spec_from_file_location(
                            fullname,
                            candidate,
                            submodule_search_locations=search_locs,
                        )
                        return spec
        return None


sys.meta_path.insert(0, _HyphenServiceFinder())


# ── 1c. Test-safe environment defaults for optional heavy services -----------
# Prevent Celery from connecting to a broker in unit tests.
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
# Prevent PostGIS singleton from trying to connect at module import time.
os.environ.setdefault("SATQUERY_SKIP_DB_INIT", "true")


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


from services.agent.tests.helpers.test_tokens import make_test_token  # noqa: E402
from tests.integration.test_p6_01_compose_integration import (
    compose_env,
    docker_available,
)  # noqa: E402

__all__ = ["make_test_token", "compose_env", "docker_available"]
