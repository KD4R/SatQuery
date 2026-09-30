"""
services/gateway/routers/dev_auth.py — Local-development sign-in.

Why this exists
---------------
The auth bypass was removed (every API route now needs a verified Bearer JWT),
but the dashboard has no identity provider wired in yet, so a local stack had no
way to obtain a token and every live call returned 401. This route issues a
short-lived HS256 token for local development only.

It is off unless ALL of these hold, and returns 404 otherwise (so a production
deployment does not even advertise it):

  * ENVIRONMENT=development
  * SATQUERY_DEV_LOGIN=1
  * AUTH_ALGORITHM=HS256 with AUTH_SECRET_KEY set (RS256/OIDC deployments sign
    tokens with a key this service does not hold, by design)

The token carries the ANALYST role in one configured organisation
(SATQUERY_DEV_ORG_ID, default "org-dev"). It is a real signed token verified by
the same code path as any other; nothing downstream special-cases it.
"""

from __future__ import annotations

import datetime
import os
import uuid

from fastapi import APIRouter, HTTPException
from jose import jwt
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/auth", tags=["auth-dev"])

#: Lifetime of a development token.
DEV_TOKEN_TTL = datetime.timedelta(hours=8)


class DevTokenRequest(BaseModel):
    email: str | None = Field(default=None, max_length=254)


class DevTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    org_id: str
    roles: list[str]


def dev_login_enabled() -> bool:
    return (
        os.getenv("ENVIRONMENT", "").strip().lower() == "development"
        and os.getenv("SATQUERY_DEV_LOGIN", "0").strip() == "1"
        and os.getenv("AUTH_ALGORITHM", "RS256").strip().upper() == "HS256"
        and bool(os.getenv("AUTH_SECRET_KEY"))
    )


@router.post("/dev-token", response_model=DevTokenResponse, include_in_schema=False)
async def issue_dev_token(body: DevTokenRequest | None = None) -> DevTokenResponse:
    if not dev_login_enabled():
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Not found", "retryable": False},
        )

    from packages.auth.config import get_auth_settings

    settings = get_auth_settings()
    org_id = os.getenv("SATQUERY_DEV_ORG_ID", "org-dev")
    roles = ["analyst"]
    now = datetime.datetime.now(datetime.timezone.utc)
    email = (body.email if body else None) or "developer@localhost"
    payload = {
        "sub": f"dev:{uuid.uuid5(uuid.NAMESPACE_DNS, email)}",
        "email": email,
        "org_id": org_id,
        "roles": roles,
        "scopes": [],
        "iat": now,
        "exp": now + DEV_TOKEN_TTL,
    }
    if settings.issuer:
        payload["iss"] = settings.issuer
    if settings.audience:
        payload["aud"] = settings.audience
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return DevTokenResponse(
        access_token=token,
        expires_in=int(DEV_TOKEN_TTL.total_seconds()),
        org_id=org_id,
        roles=roles,
    )
