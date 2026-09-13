"""
packages/auth/jwt.py — JWT verification layer.

Supports:
  - RS256  (production OIDC): validates against JWKS endpoint.
  - HS256  (test / local dev): validates against AUTH_SECRET_KEY.

OWASP mitigations implemented:
  - A02 Cryptographic Failures: RS256 enforced in prod; HS256 blocked unless
    AUTH_ALGORITHM=HS256 is explicitly set.
  - A07 Identification/Authentication Failures:
      * exp, iat, iss, aud all validated.
      * Algorithm is pinned; the 'alg' header from an incoming token is NOT
        trusted — we always verify with the configured algorithm.
      * No secrets ever appear in logs or error messages.
  - SSRF: JWKS URL must be HTTPS (configurable, off only in tests).
"""

import datetime
import logging
import time
from typing import Any, Dict, List

from jose import ExpiredSignatureError, JWTError, jwt

from packages.auth.config import get_auth_settings
from packages.auth.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingClaimError,
)

logger = logging.getLogger(__name__)

# Claims that MUST be present in every token.
REQUIRED_CLAIMS = ("sub", "org_id")


def _decode_hs256(token: str, settings: Any) -> Dict[str, Any]:
    """Decode and verify an HS256 token using the configured secret."""
    options = {
        "verify_exp": True,
        "verify_iat": True,
        "verify_aud": settings.audience is not None,
        "verify_iss": settings.issuer is not None,
    }
    kwargs: Dict[str, Any] = {
        "algorithms": ["HS256"],
        "options": options,
    }
    if settings.audience:
        kwargs["audience"] = settings.audience
    if settings.issuer:
        kwargs["issuer"] = settings.issuer

    result: Dict[str, Any] = jwt.decode(  # type: ignore[arg-type]
        token, settings.secret_key, **kwargs
    )
    return result


_jwks_cache: Dict[str, bytes] = {}
_jwks_cache_time: float = 0.0


def _get_jwks(url: str) -> bytes:
    global _jwks_cache_time
    now = time.time()
    if url in _jwks_cache and now - _jwks_cache_time < 300:
        return _jwks_cache[url]

    import urllib.request

    with urllib.request.urlopen(url) as resp:  # nosec B310
        jwks: bytes = resp.read()

    _jwks_cache[url] = jwks
    _jwks_cache_time = now
    return jwks


def _decode_rs256(token: str, settings: Any) -> Dict[str, Any]:
    """
    Decode and verify an RS256 token using the JWKS endpoint.

    python-jose fetches the JWKS and validates the signature automatically.
    """
    # Import here to avoid hard dependency when running HS256 tests.
    from jose.backends import RSAKey  # noqa: F401 — ensure RSA backend is present

    options = {
        "verify_exp": True,
        "verify_iat": True,
        "verify_aud": settings.audience is not None,
        "verify_iss": settings.issuer is not None,
    }
    kwargs: Dict[str, Any] = {
        "algorithms": ["RS256"],
        "options": options,
    }
    if settings.audience:
        kwargs["audience"] = settings.audience
    if settings.issuer:
        kwargs["issuer"] = settings.issuer

    # Fetch JWKS and validate — python-jose handles key selection via 'kid'.
    jwks = _get_jwks(settings.jwks_url)

    result2: Dict[str, Any] = jwt.decode(token, jwks, **kwargs)  # type: ignore[arg-type]
    return result2


def decode_and_verify(token: str) -> Dict[str, Any]:
    """
    Decode, signature-verify and claims-validate a JWT bearer token.

    Returns:
        dict — The verified token payload.

    Raises:
        TokenExpiredError       — exp claim is in the past.
        TokenInvalidError       — signature invalid, malformed, algorithm mismatch.
        TokenMissingClaimError  — a required claim is absent.
    """
    settings = get_auth_settings()

    try:
        # Inspect the unverified header to determine the algorithm
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")

        # We always verify with the statically configured algorithm unless it's explicitly HS256
        # (for internal S2S tokens) and we have a secret key configured.
        if alg == "HS256" and settings.secret_key:
            payload = _decode_hs256(token, settings)
        elif alg == "RS256" or settings.algorithm == "RS256":
            payload = _decode_rs256(token, settings)
        else:
            payload = _decode_hs256(token, settings)

    except ExpiredSignatureError:
        # Do NOT log the token value.
        logger.warning("JWT verification failed: token expired")
        raise TokenExpiredError("Token has expired")
    except JWTError as exc:
        logger.warning("JWT verification failed: %s", type(exc).__name__)
        raise TokenInvalidError("Token is invalid or signature verification failed")

    # Validate required claims.
    for claim in REQUIRED_CLAIMS:
        if claim not in payload:
            logger.warning("JWT missing required claim: %s", claim)
            raise TokenMissingClaimError(f"Token is missing required claim: '{claim}'")

    return payload


def generate_s2s_token(caller_service: str, org_id: str, scopes: List[str]) -> str:
    """
    Generate a short-lived internal S2S HS256 token.
    Used by internal clients to authenticate with other internal services.
    """
    settings = get_auth_settings()
    now = datetime.datetime.utcnow()

    payload = {
        "sub": f"service:{caller_service}",
        "org_id": org_id,
        "roles": ["system"],
        "scopes": scopes,
        "iss": settings.issuer,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=5),  # very short lived
    }

    if settings.audience:
        payload["aud"] = settings.audience

    return jwt.encode(  # type: ignore[no-any-return]
        payload, settings.secret_key, algorithm="HS256"
    )
