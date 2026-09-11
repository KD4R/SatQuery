"""
services/mission/dependencies.py — FastAPI dependency providers for repositories.

Overriding these in tests injects in-memory repositories without touching
the router code. Production wires up SQLAlchemy session-based repositories.
"""

from services.mission.repositories.memory import (
    InMemoryAOIRepository,
    InMemoryJobRepository,
    InMemoryMissionRepository,
)


def get_mission_repo() -> InMemoryMissionRepository:
    """
    Default: in-memory repository.
    Production override: returns SQLAlchemy-backed repository.
    """
    return InMemoryMissionRepository()


def get_aoi_repo() -> InMemoryAOIRepository:
    """Default: in-memory AOI repository."""
    return InMemoryAOIRepository()


def get_job_repo() -> InMemoryJobRepository:
    """Default: in-memory job repository."""
    return InMemoryJobRepository()
