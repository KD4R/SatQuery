"""
services/mission/domain/schemas.py — Pydantic request/response schemas.

All inputs are validated here. Field constraints enforce OWASP A03 (Injection):
  - Max lengths prevent oversized payloads.
  - Regex patterns prevent control characters in string fields.
  - GeoJSON geometry validated structurally.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from services.mission.domain.models import JobStatus, MissionStatus

# ── Shared validators ──────────────────────────────────────────────────────────
_SAFE_TEXT_RE = re.compile(r"^[^\x00-\x1f\x7f]*$")  # no control chars


def _no_control_chars(v: str) -> str:
    if v and not _SAFE_TEXT_RE.match(v):
        raise ValueError("Field must not contain control characters")
    return v


# ── GeoJSON geometry ──────────────────────────────────────────────────────────
_VALID_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
}


def _validate_geometry(v: Dict[str, Any]) -> Dict[str, Any]:
    if "type" not in v:
        raise ValueError("Geometry must have a 'type' field")
    if v["type"] not in _VALID_GEOMETRY_TYPES:
        raise ValueError(f"Geometry type must be one of {sorted(_VALID_GEOMETRY_TYPES)}")
    if v["type"] != "GeometryCollection" and "coordinates" not in v:
        raise ValueError("Geometry must have a 'coordinates' field")
    return v


# ── AOI schemas ───────────────────────────────────────────────────────────────
class AOICreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="AOI display name")
    description: Optional[str] = Field(None, max_length=2000)
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry object")

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: str) -> str:
        return _no_control_chars(v)

    @field_validator("geometry")
    @classmethod
    def geometry_valid(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        return _validate_geometry(v)


class AOIUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    geometry: Optional[Dict[str, Any]] = None

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: Optional[str]) -> Optional[str]:
        return _no_control_chars(v) if v is not None else v

    @field_validator("geometry")
    @classmethod
    def geometry_valid(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return _validate_geometry(v) if v is not None else v


class AOIResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    geometry: Dict[str, Any]
    organisation_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Mission schemas ───────────────────────────────────────────────────────────
class MissionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Mission display name")
    description: Optional[str] = Field(None, max_length=2000)
    aoi_ids: List[str] = Field(default_factory=list, max_length=50, description="AOI IDs to link")

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: str) -> str:
        return _no_control_chars(v)


class MissionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    aoi_ids: Optional[List[str]] = Field(None, max_length=50)
    status: Optional[MissionStatus] = None

    @field_validator("name")
    @classmethod
    def name_safe(cls, v: Optional[str]) -> Optional[str]:
        return _no_control_chars(v) if v is not None else v


class MissionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: MissionStatus
    aoi_ids: List[str]
    organisation_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MissionListResponse(BaseModel):
    items: List[MissionResponse]
    total: int
    limit: int
    offset: int


class AOIListResponse(BaseModel):
    items: List[AOIResponse]
    total: int
    limit: int
    offset: int


# ── Job schemas ───────────────────────────────────────────────────────────────
class JobSubmitResponse(BaseModel):
    job_id: str
    mission_id: str
    status: JobStatus
    submitted_at: datetime
    trace_id: Optional[str]
    message: str = "Job submitted. Poll /api/v1/jobs/{job_id} for status."


class JobStatusResponse(BaseModel):
    job_id: str
    mission_id: str
    status: JobStatus
    submitted_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    trace_id: Optional[str]
