"""
services/mission/dependencies.py — FastAPI dependency providers for repositories.

Overriding these in tests injects in-memory repositories without touching
the router code. Production wires up SQLAlchemy session-based repositories.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from services.mission.database import get_db_session
from services.mission.repositories.postgres import (
    PostgresAOIRepository,
    PostgresJobRepository,
    PostgresMissionRepository,
)

def get_mission_repo(session: AsyncSession = Depends(get_db_session)) -> PostgresMissionRepository:
    return PostgresMissionRepository(session)

def get_aoi_repo(session: AsyncSession = Depends(get_db_session)) -> PostgresAOIRepository:
    return PostgresAOIRepository(session)

def get_job_repo(session: AsyncSession = Depends(get_db_session)) -> PostgresJobRepository:
    return PostgresJobRepository(session)
