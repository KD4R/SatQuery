"""
packages/auth/testing.py — Test token generation helpers for integration and unit testing.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from jose import jwt
from packages.auth.config import get_auth_settings


def make_test_token(
    sub: str = "user:test",
    org_id: str = "tenant_test",
    roles: Optional[List[str]] = None,
) -> str:
    """
    Generate an HS256-signed test JWT with specified subject, organization, and roles.
    """
    settings = get_auth_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "org_id": org_id,
        "roles": roles if roles is not None else ["analyst"],
        "scopes": [],
        "iss": settings.issuer,
        "aud": settings.audience,
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    return str(jwt.encode(payload, settings.secret_key, algorithm="HS256"))
