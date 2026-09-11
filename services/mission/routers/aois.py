"""
services/mission/routers/aois.py — AOI CRUD endpoints (P1-06).

Routes:
  POST   /api/v1/aois          Create an AOI            (ANALYST+)
  GET    /api/v1/aois          List AOIs for tenant     (VIEWER+)
  GET    /api/v1/aois/{id}     Get an AOI by ID         (VIEWER+)
  DELETE /api/v1/aois/{id}     Delete an AOI            (OPERATOR+)
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.auth import get_tenant_id, require_role
from packages.auth.models import AuthContext, Role
from services.mission.domain.models import AOI
from services.mission.domain.schemas import (
    AOICreate,
    AOIListResponse,
    AOIResponse,
)
from services.mission.repositories.base import AOIRepository
from services.mission.dependencies import get_aoi_repo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/aois", tags=["aois"])


def _to_response(a: AOI) -> AOIResponse:
    return AOIResponse(
        id=a.id,
        name=a.name,
        description=a.description,
        geometry=a.geometry,
        organisation_id=a.organisation_id,
        created_by=a.created_by,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.post("", status_code=201, response_model=AOIResponse)
async def create_aoi(
    body: AOICreate,
    ctx: AuthContext = Depends(require_role(Role.ANALYST)),
    org_id: str = Depends(get_tenant_id),
    repo: AOIRepository = Depends(get_aoi_repo),
) -> AOIResponse:
    """Create a new Area of Interest."""
    aoi = AOI(
        name=body.name,
        description=body.description,
        geometry=body.geometry,
        organisation_id=org_id,
        created_by=ctx.subject,
    )
    created = await repo.create(aoi)
    logger.info("AOI created: id=%s org=%s subject=%s", created.id, org_id, ctx.subject)
    return _to_response(created)


@router.get("", response_model=AOIListResponse)
async def list_aois(
    org_id: str = Depends(get_tenant_id),
    _: AuthContext = Depends(require_role(Role.VIEWER)),
    repo: AOIRepository = Depends(get_aoi_repo),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AOIListResponse:
    """List all AOIs for the caller's tenant (paginated)."""
    items = await repo.list_by_org(org_id, limit=limit, offset=offset)
    total = await repo.count_by_org(org_id)
    return AOIListResponse(
        items=[_to_response(a) for a in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{aoi_id}", response_model=AOIResponse)
async def get_aoi(
    aoi_id: str,
    org_id: str = Depends(get_tenant_id),
    _: AuthContext = Depends(require_role(Role.VIEWER)),
    repo: AOIRepository = Depends(get_aoi_repo),
) -> AOIResponse:
    """Get a single AOI by ID (tenant-scoped)."""
    aoi = await repo.get_by_id(aoi_id, org_id)
    if aoi is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "AOI_NOT_FOUND",
                "message": f"AOI '{aoi_id}' not found.",
                "retryable": False,
            },
        )
    return _to_response(aoi)


@router.delete("/{aoi_id}", status_code=204)
async def delete_aoi(
    aoi_id: str,
    ctx: AuthContext = Depends(require_role(Role.OPERATOR)),
    org_id: str = Depends(get_tenant_id),
    repo: AOIRepository = Depends(get_aoi_repo),
) -> None:
    """Delete an AOI (OPERATOR+ only)."""
    deleted = await repo.delete(aoi_id, org_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "AOI_NOT_FOUND",
                "message": f"AOI '{aoi_id}' not found.",
                "retryable": False,
            },
        )
    logger.info("AOI deleted: id=%s org=%s subject=%s", aoi_id, org_id, ctx.subject)
