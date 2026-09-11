"""
services/mission/routers/missions.py — Mission CRUD endpoints (P1-06).

Routes:
  POST   /api/v1/missions          Create a mission            (ANALYST+)
  GET    /api/v1/missions          List missions for tenant    (VIEWER+)
  GET    /api/v1/missions/{id}     Get a mission by ID         (VIEWER+)
  PATCH  /api/v1/missions/{id}     Update a mission            (OPERATOR+)
  DELETE /api/v1/missions/{id}     Delete a mission            (ADMIN)

OWASP mitigations:
  A01 — All routes gated by require_role; tenant isolation via get_tenant_id.
  A03 — All inputs validated by Pydantic schemas with field constraints.
  A04 — Mission lookups always include organisation_id — cross-tenant impossible.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.auth import get_tenant_id, require_role
from packages.auth.models import AuthContext, Role
from services.mission.domain.models import Mission, MissionStatus
from services.mission.domain.schemas import (
    MissionCreate,
    MissionListResponse,
    MissionResponse,
    MissionUpdate,
)
from services.mission.repositories.base import MissionRepository
from services.mission.dependencies import get_mission_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/missions", tags=["missions"])


def _to_response(m: Mission) -> MissionResponse:
    return MissionResponse(
        id=m.id,
        name=m.name,
        description=m.description,
        status=m.status,
        aoi_ids=m.aoi_ids,
        organisation_id=m.organisation_id,
        created_by=m.created_by,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.post("", status_code=201, response_model=MissionResponse)
async def create_mission(
    body: MissionCreate,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
    org_id: str = Depends(get_tenant_id),
    repo: MissionRepository = Depends(get_mission_repo),
) -> MissionResponse:
    """Create a new Mission within the caller's tenant."""
    mission = Mission(
        name=body.name,
        description=body.description,
        aoi_ids=body.aoi_ids,
        organisation_id=org_id,
        created_by=ctx.subject,
        status=MissionStatus.DRAFT,
    )
    created = await repo.create(mission)
    logger.info(
        "Mission created: id=%s org=%s subject=%s",
        created.id,
        org_id,
        ctx.subject,
    )
    return _to_response(created)


@router.get("", response_model=MissionListResponse)
async def list_missions(
    org_id: str = Depends(get_tenant_id),
    _: AuthContext = Depends(require_role(Role.VIEWER)),
    repo: MissionRepository = Depends(get_mission_repo),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MissionListResponse:
    """List all Missions for the caller's tenant (paginated)."""
    items = await repo.list_by_org(org_id, limit=limit, offset=offset)
    total = await repo.count_by_org(org_id)
    return MissionListResponse(
        items=[_to_response(m) for m in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: str,
    org_id: str = Depends(get_tenant_id),
    _: AuthContext = Depends(require_role(Role.VIEWER)),
    repo: MissionRepository = Depends(get_mission_repo),
) -> MissionResponse:
    """Get a single Mission by ID (tenant-scoped)."""
    mission = await repo.get_by_id(mission_id, org_id)
    if mission is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MISSION_NOT_FOUND",
                "message": f"Mission '{mission_id}' not found.",
                "retryable": False,
            },
        )
    return _to_response(mission)


@router.patch("/{mission_id}", response_model=MissionResponse)
async def update_mission(
    mission_id: str,
    body: MissionUpdate,
    ctx: AuthContext = Depends(require_role(Role.OPERATOR)),
    org_id: str = Depends(get_tenant_id),
    repo: MissionRepository = Depends(get_mission_repo),
) -> MissionResponse:
    """Update a Mission's fields (OPERATOR+ only)."""
    mission = await repo.get_by_id(mission_id, org_id)
    if mission is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MISSION_NOT_FOUND",
                "message": f"Mission '{mission_id}' not found.",
                "retryable": False,
            },
        )

    # Apply partial updates
    if body.name is not None:
        mission.name = body.name
    if body.description is not None:
        mission.description = body.description
    if body.aoi_ids is not None:
        mission.aoi_ids = body.aoi_ids
    if body.status is not None:
        mission.status = body.status
    mission.updated_at = datetime.now(timezone.utc)

    updated = await repo.update(mission)
    logger.info(
        "Mission updated: id=%s org=%s subject=%s",
        mission_id,
        org_id,
        ctx.subject,
    )
    return _to_response(updated)


@router.delete("/{mission_id}", status_code=204)
async def delete_mission(
    mission_id: str,
    ctx: AuthContext = Depends(require_role(Role.ADMIN)),
    org_id: str = Depends(get_tenant_id),
    repo: MissionRepository = Depends(get_mission_repo),
) -> None:
    """Delete a Mission (ADMIN only)."""
    deleted = await repo.delete(mission_id, org_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "MISSION_NOT_FOUND",
                "message": f"Mission '{mission_id}' not found.",
                "retryable": False,
            },
        )
    logger.info(
        "Mission deleted: id=%s org=%s subject=%s",
        mission_id,
        org_id,
        ctx.subject,
    )
