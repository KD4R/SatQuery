"""
packages/auth — OAuth2/OIDC JWT verification, RBAC and tenant isolation.

Public surface:
    get_current_user   — FastAPI dependency: returns verified AuthContext
    require_role       — FastAPI dependency factory: enforces minimum role
    get_tenant_id      — FastAPI dependency: returns organisation_id from token
    AuthContext        — Pydantic model holding all claims from a verified token
    Role               — Enum of all platform roles
    Permission         — Enum of all fine-grained permissions
    has_permission     — Check whether a role grants a permission
"""

from packages.auth.models import AuthContext, Role, Permission
from packages.auth.dependencies import get_current_user, require_role, get_tenant_id
from packages.auth.rbac import has_permission

__all__ = [
    "AuthContext",
    "Role",
    "Permission",
    "get_current_user",
    "require_role",
    "get_tenant_id",
    "has_permission",
]
