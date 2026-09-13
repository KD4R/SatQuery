from sqlalchemy import Column, String, DateTime, JSON, Enum as SQLEnum
from services.mission.database import Base
from services.mission.domain.models import MissionStatus, JobStatus
from datetime import datetime, timezone

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

class MissionModel(Base):
    __tablename__ = "missions"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(SQLEnum(MissionStatus), default=MissionStatus.DRAFT, nullable=False)
    aoi_ids = Column(JSON, default=list, nullable=False)
    organisation_id = Column(String, index=True, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now, nullable=False)

class AOIModel(Base):
    __tablename__ = "aois"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    geometry = Column(JSON, nullable=False)
    organisation_id = Column(String, index=True, nullable=False)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now, nullable=False)

class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    mission_id = Column(String, index=True, nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    organisation_id = Column(String, index=True, nullable=False)
    submitted_by = Column(String, nullable=False)
    submitted_at = Column(DateTime, default=_utc_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    trace_id = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
