"""
packages/auth/dependencies.py — FastAPI dependency injection for auth.

Usage in a route handler:

    from packages.auth import get_current_user, require_role, get_tenant_id
    from packages.auth.models import Role

    @router.get("/missions")
    async def list_missions(
        ctx: AuthContext = Depends(get_current_user),
        _: None = Depends(require_role(Role.ANALYST)),
        org_id: str = Depends(get_tenant_id),
    ):
        ...

OWASP mitigations:
  - Bearer token is extracted only from the Authorization header (not query params).
  - Errors return canonical ErrorResponse — no stack traces or internal details.
  - No secrets appear in responses or logs.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from packages.auth.exceptions import (
    AuthError,
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingClaimError,
)
from packages.auth.jwt import decode_and_verify
from packages.auth.models import AuthContext, Role
from packages.auth.rbac import has_permission  # noqa: F401 — re-exported

logger = logging.getLogger(__name__)

# Scheme — auto_error=False so we return a canonical 401 ourselves.
_bearer_scheme = HTTPBearer(auto_error=False)


def _build_auth_context(payload: dict, trace_id: Optional[str] = None) -> AuthContext:
    """Build an AuthContext from a verified JWT payload."""
    raw_roles = payload.get("roles", [])
    roles = []
    for r in raw_roles:
        try:
            roles.append(Role(r))
        except ValueError:
            logger.warning("Unknown role in token, skipping: %s", r)

    return AuthContext(
        subject=payload["sub"],
        email=payload.get("email"),
        organisation_id=payload["org_id"],
        roles=roles,
        trace_id=trace_id,
        raw_claims=payload,
    )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthContext:
    """
    FastAPI dependency — extract, verify and return the caller's AuthContext.

    Raises HTTP 401 if the token is absent, expired or invalid.
    """
    trace_id: Optional[str] = request.headers.get("X-Trace-Id")

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_MISSING",
                "message": "Authorization header with Bearer token is required",
                "retryable": False,
                "trace_id": trace_id,
            },
        )

    token = credentials.credentials

    try:
        payload = decode_and_verify(token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_EXPIRED",
                "message": "Token has expired. Please re-authenticate.",
                "retryable": False,
                "trace_id": trace_id,
            },
        )
    except (TokenInvalidError, TokenMissingClaimError):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TOKEN_INVALID",
                "message": "Token is invalid or missing required claims.",
                "retryable": False,
                "trace_id": trace_id,
            },
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "code": exc.error_code,
                "message": "Authentication failed.",
                "retryable": False,
                "trace_id": trace_id,
            },
        )

    return _build_auth_context(payload, trace_id)


def require_role(minimum_role: Role):
    """
    FastAPI dependency factory — enforces that the caller holds at least
    *minimum_role*. Raises HTTP 403 on failure.

    Example:
        Depends(require_role(Role.OPERATOR))
    """

    async def _check(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not ctx.has_role(minimum_role) and not ctx.is_admin:
            logger.warning(
                "Access denied: subject=%s org=%s required_role=%s actual_roles=%s",
                ctx.subject,
                ctx.organisation_id,
                minimum_role,
                ctx.roles,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": f"Role '{minimum_role.value}' or higher is required.",
                    "retryable": False,
                },
            )
        return ctx

    return _check


async def get_tenant_id(ctx: AuthContext = Depends(get_current_user)) -> str:
    """
    FastAPI dependency — return the verified organisation_id (tenant scope).

    Use this in every DB query to enforce tenant isolation.
    """
    return ctx.organisation_id
