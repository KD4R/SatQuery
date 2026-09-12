"""
packages/auth/exceptions.py — Canonical auth exception hierarchy.

All exceptions map to a specific HTTP status and canonical ErrorResponse code.
"""


class AuthError(Exception):
    """Base class for all authentication/authorisation errors."""

    http_status: int = 401
    error_code: str = "AUTH_ERROR"


class TokenExpiredError(AuthError):
    """The JWT exp claim is in the past."""

    error_code = "TOKEN_EXPIRED"


class TokenInvalidError(AuthError):
    """The JWT signature is invalid or the token is malformed."""

    error_code = "TOKEN_INVALID"


class TokenMissingClaimError(AuthError):
    """A required claim is missing from the verified token."""

    error_code = "TOKEN_MISSING_CLAIM"


class InsufficientPermissionsError(AuthError):
    """The caller's roles do not grant the required permission."""

    http_status = 403
    error_code = "INSUFFICIENT_PERMISSIONS"


class TenantMismatchError(AuthError):
    """The requested resource belongs to a different tenant."""

    http_status = 403
    error_code = "TENANT_MISMATCH"
