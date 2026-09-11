"""
packages/auth/rbac.py — Role-Based Access Control (RBAC) engine.

Design:
  - Role → Permission mapping is explicit and deny-by-default.
  - SYSTEM role is granted every permission (machine-to-machine).
  - ADMIN role is granted every permission within their tenant.
  - Roles are additive: a user's effective permissions = union of all their roles.

OWASP A01:2021 Broken Access Control mitigations:
  - All permission checks are centralised here (no ad-hoc if-role checks).
  - has_permission() is the single gate — no bypasses.
  - Tenant isolation is enforced separately in dependencies.py.
"""

from typing import Dict, FrozenSet, Set

from packages.auth.models import Permission, Role

# ── Role → Permission matrix ──────────────────────────────────────────────────
_ROLE_PERMISSIONS: Dict[Role, FrozenSet[Permission]] = {
    Role.VIEWER: frozenset(
        {
            Permission.MISSION_READ,
            Permission.AOI_READ,
        }
    ),
    Role.ANALYST: frozenset(
        {
            Permission.MISSION_READ,
            Permission.MISSION_CREATE,
            Permission.AOI_READ,
            Permission.AOI_CREATE,
            Permission.JOB_SUBMIT,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Permission.MISSION_READ,
            Permission.MISSION_CREATE,
            Permission.MISSION_UPDATE,
            Permission.AOI_READ,
            Permission.AOI_CREATE,
            Permission.AOI_UPDATE,
            Permission.JOB_SUBMIT,
            Permission.JOB_CANCEL,
        }
    ),
    Role.ADMIN: frozenset(Permission),  # all permissions
    Role.SYSTEM: frozenset(Permission),  # all permissions
}


def effective_permissions(roles: list) -> Set[Permission]:
    """
    Return the union of all permissions granted by the given list of roles.
    """
    result: Set[Permission] = set()
    for role in roles:
        result |= _ROLE_PERMISSIONS.get(role, frozenset())
    return result


def has_permission(roles: list, permission: Permission) -> bool:
    """
    Return True if any role in *roles* grants *permission*.

    Args:
        roles:      List of Role values from AuthContext.roles.
        permission: The Permission being checked.

    Returns:
        bool — True if granted, False otherwise.
    """
    return permission in effective_permissions(roles)
