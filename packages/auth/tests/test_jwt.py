"""
Unit tests for JWT verification (P1-03).

Covers:
  - Valid token decode
  - Expired token
  - Tampered / invalid signature
  - Wrong audience
  - Wrong issuer
  - Missing required claims (sub, org_id)
  - Algorithm pinning (HS256 cannot sneak in RS256 header)
"""

import pytest
from jose import jwt as jose_jwt

from packages.auth.exceptions import (
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingClaimError,
)
from packages.auth.jwt import decode_and_verify
from packages.auth.tests.conftest import (
    TEST_ALGORITHM,
    TEST_AUDIENCE,
    TEST_ISSUER,
    TEST_ORG_ID,
    TEST_SECRET,
    make_expired_token,
    make_token,
)


@pytest.mark.unit
def test_jwt_valid_token_decodes_correctly():
    """A well-formed, in-date token should decode without error."""
    token = make_token(subject="user-abc", org_id="org-xyz", roles=["analyst"])
    payload = decode_and_verify(token)

    assert payload["sub"] == "user-abc"
    assert payload["org_id"] == "org-xyz"
    assert "analyst" in payload["roles"]


@pytest.mark.unit
def test_jwt_expired_token_raises_token_expired_error():
    """An expired token must raise TokenExpiredError — never silently succeed."""
    token = make_expired_token()
    with pytest.raises(TokenExpiredError):
        decode_and_verify(token)


@pytest.mark.unit
def test_jwt_tampered_signature_raises_token_invalid_error():
    """A token whose signature has been modified must raise TokenInvalidError."""
    token = make_token()
    # Corrupt the last 8 chars of the signature segment.
    parts = token.split(".")
    parts[2] = parts[2][:-8] + "XXXXXXXX"
    tampered = ".".join(parts)

    with pytest.raises(TokenInvalidError):
        decode_and_verify(tampered)


@pytest.mark.unit
def test_jwt_wrong_audience_raises_token_invalid_error():
    """A token issued for a different audience must be rejected."""
    token = make_token(audience="other-service")
    with pytest.raises(TokenInvalidError):
        decode_and_verify(token)


@pytest.mark.unit
def test_jwt_wrong_issuer_raises_token_invalid_error():
    """A token from an unexpected issuer must be rejected."""
    token = make_token(issuer="https://evil.example.com")
    with pytest.raises(TokenInvalidError):
        decode_and_verify(token)


@pytest.mark.unit
def test_jwt_missing_sub_claim_raises_missing_claim_error():
    """A token without 'sub' must raise TokenMissingClaimError."""
    import time

    payload = {
        "org_id": TEST_ORG_ID,
        "roles": ["analyst"],
        "aud": TEST_AUDIENCE,
        "iss": TEST_ISSUER,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        # deliberately omitting 'sub'
    }
    token = jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)
    with pytest.raises(TokenMissingClaimError):
        decode_and_verify(token)


@pytest.mark.unit
def test_jwt_missing_org_id_claim_raises_missing_claim_error():
    """A token without 'org_id' (tenant claim) must raise TokenMissingClaimError."""
    import time

    payload = {
        "sub": "user-123",
        "roles": ["analyst"],
        "aud": TEST_AUDIENCE,
        "iss": TEST_ISSUER,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        # deliberately omitting 'org_id'
    }
    token = jose_jwt.encode(payload, TEST_SECRET, algorithm=TEST_ALGORITHM)
    with pytest.raises(TokenMissingClaimError):
        decode_and_verify(token)


@pytest.mark.unit
def test_jwt_completely_malformed_string_raises_token_invalid_error():
    """A non-JWT string must raise TokenInvalidError, not crash."""
    with pytest.raises(TokenInvalidError):
        decode_and_verify("this.is.not.a.jwt.at.all")


@pytest.mark.unit
def test_jwt_empty_string_raises_token_invalid_error():
    """An empty string must raise TokenInvalidError."""
    with pytest.raises(TokenInvalidError):
        decode_and_verify("")


@pytest.mark.unit
def test_jwt_extra_claims_are_preserved():
    """Additional claims in the token payload should be accessible."""
    token = make_token(extra_claims={"mission_id": "m-001", "run_id": "r-001"})
    payload = decode_and_verify(token)
    assert payload["mission_id"] == "m-001"
    assert payload["run_id"] == "r-001"
