from typing import Any
from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum
from services.mission.database import Base
from services.mission.domain.models import MissionStatus, JobStatus
from datetime import datetime, timezone

# The repositories and routers stamp timezone-aware UTC datetimes
# (datetime.now(timezone.utc)); naive columns made asyncpg reject every INSERT
# ("can't subtract offset-naive and offset-aware datetimes"). These are
# timestamptz columns, matching what the code actually produces.
TIMESTAMP = DateTime(timezone=True)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MissionModel(Base):
    __tablename__ = "missions"

    id: Any = Column(String, primary_key=True, index=True)
    name: Any = Column(String, nullable=False)
    description: Any = Column(String, nullable=True)
    status: Any = Column(SQLEnum(MissionStatus), default=MissionStatus.DRAFT, nullable=False)
    aoi_ids: Any = Column(JSON, default=list, nullable=False)
    organisation_id: Any = Column(String, index=True, nullable=False)
    created_by: Any = Column(String, nullable=False)
    created_at: Any = Column(TIMESTAMP, default=_utc_now, nullable=False)
    updated_at: Any = Column(TIMESTAMP, default=_utc_now, onupdate=_utc_now, nullable=False)


class AOIModel(Base):
    __tablename__ = "aois"

    id: Any = Column(String, primary_key=True, index=True)
    name: Any = Column(String, nullable=False)
    description: Any = Column(String, nullable=True)
    geometry: Any = Column(JSON, nullable=False)
    organisation_id: Any = Column(String, index=True, nullable=False)
    created_by: Any = Column(String, nullable=False)
    created_at: Any = Column(TIMESTAMP, default=_utc_now, nullable=False)
    updated_at: Any = Column(TIMESTAMP, default=_utc_now, onupdate=_utc_now, nullable=False)


class JobModel(Base):
    __tablename__ = "jobs"

    id: Any = Column(String, primary_key=True, index=True)
    mission_id: Any = Column(String, index=True, nullable=False)
    status: Any = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    organisation_id: Any = Column(String, index=True, nullable=False)
    submitted_by: Any = Column(String, nullable=False)
    submitted_at: Any = Column(TIMESTAMP, default=_utc_now, nullable=False)
    started_at: Any = Column(TIMESTAMP, nullable=True)
    completed_at: Any = Column(TIMESTAMP, nullable=True)
    trace_id: Any = Column(String, nullable=True)
    error_message: Any = Column(String, nullable=True)
