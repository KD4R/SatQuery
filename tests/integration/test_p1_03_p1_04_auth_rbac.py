"""
Integration tests for P1-03/P1-04: Auth + RBAC on a protected Gateway endpoint.

Strategy:
  - Add a /api/v1/me protected endpoint to the Gateway for this test.
  - Drive it with a TestClient and fabricated JWT tokens.
  - Verify 200 with valid token, 401 with missing/expired/invalid token,
    403 with wrong role, and tenant isolation via the org_id claim.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from packages.auth import get_current_user, get_tenant_id, require_role
from packages.auth.models import AuthContext, Role
from packages.auth.tests.conftest import (
    make_expired_token,
    make_token,
)

# ── Minimal protected app for integration tests ───────────────────────────────
_app = FastAPI()


@_app.get("/api/v1/me")
async def me(ctx: AuthContext = Depends(get_current_user)):
    return {
        "subject": ctx.subject,
        "organisation_id": ctx.organisation_id,
        "roles": [r.value for r in ctx.roles],
    }


@_app.get("/api/v1/admin-only")
async def admin_only(_: AuthContext = Depends(require_role(Role.ADMIN))):
    return {"message": "Welcome, admin"}


@_app.get("/api/v1/tenant-id")
async def get_org(org_id: str = Depends(get_tenant_id)):
    return {"organisation_id": org_id}


@pytest.fixture(scope="module")
def protected_client():
    with TestClient(_app) as c:
        yield c


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Happy path ────────────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_03_valid_token_returns_200(protected_client):
    """A valid JWT grants access and returns correct identity claims."""
    token = make_token(subject="user-abc", org_id="org-001", roles=["analyst"])
    resp = protected_client.get("/api/v1/me", headers=_auth_header(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject"] == "user-abc"
    assert body["organisation_id"] == "org-001"
    assert "analyst" in body["roles"]


@pytest.mark.integration
def test_p1_03_get_tenant_id_returns_org_id(protected_client):
    """get_tenant_id dependency returns the org_id from the verified token."""
    token = make_token(org_id="org-tenant-42")
    resp = protected_client.get("/api/v1/tenant-id", headers=_auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["organisation_id"] == "org-tenant-42"


# ── Auth failures (401) ───────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_03_missing_auth_header_returns_401(protected_client):
    """Requests without Authorization header are rejected with 401."""
    resp = protected_client.get("/api/v1/me")
    assert resp.status_code == 401


@pytest.mark.integration
def test_p1_03_expired_token_returns_401(protected_client):
    """An expired token must be rejected with 401."""
    token = make_expired_token()
    resp = protected_client.get("/api/v1/me", headers=_auth_header(token))
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.integration
def test_p1_03_tampered_token_returns_401(protected_client):
    """A token with a modified signature must be rejected with 401."""
    token = make_token()
    parts = token.split(".")
    parts[2] = parts[2][:-8] + "TAMPERED"
    tampered = ".".join(parts)
    resp = protected_client.get("/api/v1/me", headers=_auth_header(tampered))
    assert resp.status_code == 401


@pytest.mark.integration
def test_p1_03_garbage_token_returns_401(protected_client):
    """A completely invalid string as a bearer token must return 401."""
    resp = protected_client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


# ── RBAC failures (403) ───────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_04_insufficient_role_returns_403(protected_client):
    """A VIEWER calling an ADMIN-only endpoint must receive 403."""
    token = make_token(roles=["viewer"])
    resp = protected_client.get("/api/v1/admin-only", headers=_auth_header(token))
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.integration
def test_p1_04_admin_role_passes_rbac_gate(protected_client):
    """An ADMIN token must be accepted by the admin-only endpoint."""
    token = make_token(roles=["admin"])
    resp = protected_client.get("/api/v1/admin-only", headers=_auth_header(token))
    assert resp.status_code == 200


# ── Tenant isolation ──────────────────────────────────────────────────────────
@pytest.mark.integration
def test_p1_04_tenant_isolation_org_ids_do_not_leak(protected_client):
    """Two calls with different org_ids must return different organisation_ids."""
    token_a = make_token(org_id="org-alpha")
    token_b = make_token(org_id="org-beta")

    resp_a = protected_client.get("/api/v1/tenant-id", headers=_auth_header(token_a))
    resp_b = protected_client.get("/api/v1/tenant-id", headers=_auth_header(token_b))

    assert resp_a.json()["organisation_id"] == "org-alpha"
    assert resp_b.json()["organisation_id"] == "org-beta"
    assert resp_a.json()["organisation_id"] != resp_b.json()["organisation_id"]
