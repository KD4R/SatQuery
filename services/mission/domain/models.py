"""
services/mission/domain/models.py — Pure domain models for Mission and AOI.

These are the authoritative in-memory representations — no ORM annotations here.
Repository layer is responsible for persistence mapping.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class MissionStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AOI:
    """Area of Interest — defines a geospatial region for a Mission."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    description: Optional[str] = None
    # GeoJSON Geometry object (type + coordinates)
    geometry: Dict[str, Any] = field(default_factory=dict)
    organisation_id: str = ""
    created_by: str = ""  # subject claim from JWT
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass
class Mission:
    """Mission — a named satellite observation task."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    description: Optional[str] = None
    status: MissionStatus = MissionStatus.DRAFT
    aoi_ids: List[str] = field(default_factory=list)
    organisation_id: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass
class Job:
    """Job — an async run triggered for a Mission."""

    id: str = field(default_factory=_new_id)
    mission_id: str = ""
    status: JobStatus = JobStatus.PENDING
    organisation_id: str = ""
    submitted_by: str = ""
    submitted_at: datetime = field(default_factory=_utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    trace_id: Optional[str] = None
    error_message: Optional[str] = None
