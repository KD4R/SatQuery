"""
Unit tests for RBAC engine and tenant isolation (P1-04).

Covers:
  - Role-permission matrix correctness
  - Additive permissions (union across multiple roles)
  - Deny-by-default for unknown/unlisted permissions
  - ADMIN / SYSTEM bypass
  - has_permission() edge cases
  - AuthContext.is_admin / is_system / has_role helpers
"""

import pytest

from packages.auth.models import AuthContext, Permission, Role
from packages.auth.rbac import effective_permissions, has_permission
from packages.auth.tests.conftest import TEST_ORG_ID


# ── Helper ────────────────────────────────────────────────────────────────────
def ctx(roles: list, org_id: str = TEST_ORG_ID) -> AuthContext:
    return AuthContext(
        subject="user-test",
        email="u@test.com",
        organisation_id=org_id,
        roles=roles,
        trace_id=None,
        raw_claims={},
    )


# ── Role permission matrix ────────────────────────────────────────────────────
@pytest.mark.unit
def test_rbac_viewer_can_only_read():
    """VIEWER role must only grant read permissions."""
    perms = effective_permissions([Role.VIEWER])
    assert Permission.MISSION_READ in perms
    assert Permission.AOI_READ in perms
    # Must NOT have write permissions
    assert Permission.MISSION_CREATE not in perms
    assert Permission.JOB_SUBMIT not in perms
    assert Permission.TENANT_MANAGE not in perms


@pytest.mark.unit
def test_rbac_analyst_can_create_and_submit():
    """ANALYST role must grant create and job-submit permissions."""
    perms = effective_permissions([Role.ANALYST])
    assert Permission.MISSION_CREATE in perms
    assert Permission.AOI_CREATE in perms
    assert Permission.JOB_SUBMIT in perms
    # Must NOT have delete or admin permissions
    assert Permission.MISSION_DELETE not in perms
    assert Permission.TENANT_MANAGE not in perms


@pytest.mark.unit
def test_rbac_operator_can_cancel_jobs():
    """OPERATOR role must include JOB_CANCEL on top of ANALYST permissions."""
    perms = effective_permissions([Role.OPERATOR])
    assert Permission.JOB_CANCEL in perms
    assert Permission.MISSION_UPDATE in perms
    assert Permission.TENANT_MANAGE not in perms


@pytest.mark.unit
def test_rbac_admin_has_all_permissions():
    """ADMIN role must grant every permission."""
    perms = effective_permissions([Role.ADMIN])
    for p in Permission:
        assert p in perms, f"ADMIN is missing permission: {p}"


@pytest.mark.unit
def test_rbac_system_has_all_permissions():
    """SYSTEM role must grant every permission (machine-to-machine)."""
    perms = effective_permissions([Role.SYSTEM])
    for p in Permission:
        assert p in perms, f"SYSTEM is missing permission: {p}"


# ── Additive permissions ───────────────────────────────────────────────────────
@pytest.mark.unit
def test_rbac_roles_are_additive():
    """A user with both VIEWER and ANALYST gets the union of permissions."""
    perms = effective_permissions([Role.VIEWER, Role.ANALYST])
    assert Permission.MISSION_READ in perms
    assert Permission.MISSION_CREATE in perms
    assert Permission.JOB_SUBMIT in perms


# ── has_permission() ──────────────────────────────────────────────────────────
@pytest.mark.unit
def test_rbac_has_permission_returns_true_when_granted():
    assert has_permission([Role.ANALYST], Permission.MISSION_CREATE) is True


@pytest.mark.unit
def test_rbac_has_permission_returns_false_when_not_granted():
    assert has_permission([Role.VIEWER], Permission.MISSION_CREATE) is False


@pytest.mark.unit
def test_rbac_has_permission_empty_roles_denies_all():
    """No roles → no permissions (deny by default)."""
    for p in Permission:
        assert has_permission([], p) is False


# ── AuthContext helpers ───────────────────────────────────────────────────────
@pytest.mark.unit
def test_auth_context_is_admin_true_for_admin():
    assert ctx([Role.ADMIN]).is_admin is True


@pytest.mark.unit
def test_auth_context_is_admin_true_for_system():
    assert ctx([Role.SYSTEM]).is_admin is True


@pytest.mark.unit
def test_auth_context_is_admin_false_for_analyst():
    assert ctx([Role.ANALYST]).is_admin is False


@pytest.mark.unit
def test_auth_context_is_system_true_for_system():
    assert ctx([Role.SYSTEM]).is_system is True


@pytest.mark.unit
def test_auth_context_is_system_false_for_admin():
    assert ctx([Role.ADMIN]).is_system is False


@pytest.mark.unit
def test_auth_context_has_role():
    c = ctx([Role.ANALYST])
    assert c.has_role(Role.ANALYST) is True
    assert c.has_role(Role.ADMIN) is False


# ── Tenant isolation model ─────────────────────────────────────────────────────
@pytest.mark.unit
def test_tenant_isolation_different_org_ids_are_distinct():
    """Two AuthContexts with different org IDs must not share state."""
    c1 = ctx([Role.ANALYST], org_id="org-alpha")
    c2 = ctx([Role.ANALYST], org_id="org-beta")
    assert c1.organisation_id != c2.organisation_id


@pytest.mark.unit
def test_tenant_isolation_org_id_is_always_set():
    """organisation_id must be a non-empty string."""
    c = ctx([Role.VIEWER], org_id="org-001")
    assert c.organisation_id
    assert len(c.organisation_id) > 0


# ── Role hierarchy ─────────────────────────────────────────────────────────────
#
# Role's docstring says the roles are ordered and each inherits the ones below it,
# and require_role() promises "at least" the minimum. has_role() was exact
# membership, so an analyst was refused every VIEWER route -- /agent/tools,
# /agent/runs/{id}, GET /missions, the inference model registry. It surfaced only
# when a human token was used end to end: S2S tokens carry `system`, and is_admin
# waves those through, so the proxy chain worked throughout.


@pytest.mark.unit
@pytest.mark.parametrize(
    "held,required,expected",
    [
        (Role.ANALYST, Role.VIEWER, True),
        (Role.OPERATOR, Role.ANALYST, True),
        (Role.OPERATOR, Role.VIEWER, True),
        (Role.ADMIN, Role.OPERATOR, True),
        (Role.SYSTEM, Role.ADMIN, True),
        (Role.VIEWER, Role.ANALYST, False),
        (Role.ANALYST, Role.OPERATOR, False),
        (Role.OPERATOR, Role.ADMIN, False),
        (Role.ADMIN, Role.SYSTEM, False),
    ],
)
def test_role_hierarchy_inherits_downward_only(held, required, expected) -> None:
    assert ctx([held]).has_role(required) is expected


@pytest.mark.unit
def test_every_role_satisfies_itself() -> None:
    for role in Role:
        assert ctx([role]).has_role(role) is True


@pytest.mark.unit
def test_an_unrecognised_role_grants_nothing() -> None:
    """A token from a future service carrying a role this build does not know must
    not satisfy a check by accident. It ranks below everything, including VIEWER."""
    c = ctx([])
    c.roles = ["wizard"]  # type: ignore[list-item]
    assert c.has_role(Role.VIEWER) is False
