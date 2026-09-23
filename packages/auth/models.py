"""
packages/auth/models.py — Domain models for auth context, roles and permissions.

AuthContext is the single source of truth for identity throughout the platform.
Every service handler receives it as a FastAPI dependency.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Role(str, Enum):
    """
    Platform roles — ordered from least to most privileged.
    Every role implicitly inherits the permissions of all roles below it.
    """

    VIEWER = "viewer"  # read-only access to missions / results
    ANALYST = "analyst"  # can create missions and run analyses
    OPERATOR = "operator"  # can manage AOIs and approve jobs
    ADMIN = "admin"  # full tenant administration
    SYSTEM = "system"  # machine-to-machine service accounts


#: Privilege order, low to high. The single place the hierarchy is written down.
_ROLE_RANK: dict["Role", int] = {
    Role.VIEWER: 0,
    Role.ANALYST: 1,
    Role.OPERATOR: 2,
    Role.ADMIN: 3,
    Role.SYSTEM: 4,
}


class Permission(str, Enum):
    """Fine-grained permissions checked at the handler level."""

    # Mission
    MISSION_READ = "mission:read"
    MISSION_CREATE = "mission:create"
    MISSION_UPDATE = "mission:update"
    MISSION_DELETE = "mission:delete"

    # AOI
    AOI_READ = "aoi:read"
    AOI_CREATE = "aoi:create"
    AOI_UPDATE = "aoi:update"
    AOI_DELETE = "aoi:delete"

    # Jobs
    JOB_SUBMIT = "job:submit"
    JOB_CANCEL = "job:cancel"

    # Admin
    TENANT_MANAGE = "tenant:manage"
    USER_MANAGE = "user:manage"


class AuthContext(BaseModel):
    """
    Verified identity context extracted from a validated JWT.
    Passed as a dependency into every protected handler.

    Security guarantees:
      - All fields are populated from a cryptographically verified JWT.
      - organisation_id enforces tenant isolation in every DB query.
      - roles is normalised to the canonical Role enum.
      - subject is the stable, unique user identifier (never email alone).
    """

    subject: str = Field(..., description="JWT 'sub' — stable unique user ID")
    email: Optional[str] = Field(None, description="User email from token claims")
    organisation_id: str = Field(..., description="Tenant identifier from 'org_id' claim")
    roles: List[Role] = Field(default_factory=list, description="Roles granted to the user")
    scopes: List[str] = Field(default_factory=list, description="Scopes (primarily for S2S tokens)")
    trace_id: Optional[str] = Field(None, description="Inbound trace ID (for correlation)")
    raw_claims: dict = Field(default_factory=dict, description="Full decoded JWT payload")

    @property
    def is_admin(self) -> bool:
        return Role.ADMIN in self.roles or Role.SYSTEM in self.roles

    @property
    def is_system(self) -> bool:
        return Role.SYSTEM in self.roles

    def has_role(self, role: Role) -> bool:
        """Return True if the context holds *at least* this role.

        Ranked, not exact membership. Role's own docstring says the roles are
        "ordered from least to most privileged" and that each "implicitly inherits
        the permissions of all roles below it", and require_role() promises "at
        least *minimum_role*" -- but this was a plain `role in self.roles`, so an
        analyst was refused every VIEWER route: /agent/tools, /agent/runs/{id},
        GET /missions, and the inference registry among them. Service-to-service
        calls were unaffected, because S2S tokens carry `system` and is_admin lets
        those through, which is why the proxy chain worked and this did not show up
        until a human token was used end to end.

        An unknown role ranks below everything rather than raising: a token minted
        by a future service with a role this build has not heard of must not be
        able to satisfy a check by accident.
        """
        held = max((_ROLE_RANK.get(r, -1) for r in self.roles), default=-1)
        return held >= _ROLE_RANK[role]

    model_config = {"use_enum_values": False}
