"""
services/mission/repositories/base.py — Abstract repository interfaces.

Using Protocol (structural subtyping) so implementations can be swapped
without inheritance coupling. In-memory implementations for tests,
SQLAlchemy implementations for production.
"""

from typing import List, Optional, Protocol, runtime_checkable

from services.mission.domain.models import AOI, Job, Mission


@runtime_checkable
class MissionRepository(Protocol):
    async def create(self, mission: Mission) -> Mission: ...

    async def get_by_id(self, mission_id: str, organisation_id: str) -> Optional[Mission]: ...

    async def list_by_org(
        self, organisation_id: str, limit: int = 50, offset: int = 0
    ) -> List[Mission]: ...

    async def count_by_org(self, organisation_id: str) -> int: ...

    async def update(self, mission: Mission) -> Mission: ...

    async def delete(self, mission_id: str, organisation_id: str) -> bool: ...


@runtime_checkable
class AOIRepository(Protocol):
    async def create(self, aoi: AOI) -> AOI: ...

    async def get_by_id(self, aoi_id: str, organisation_id: str) -> Optional[AOI]: ...

    async def list_by_org(
        self, organisation_id: str, limit: int = 50, offset: int = 0
    ) -> List[AOI]: ...

    async def count_by_org(self, organisation_id: str) -> int: ...

    async def delete(self, aoi_id: str, organisation_id: str) -> bool: ...


@runtime_checkable
class JobRepository(Protocol):
    async def create(self, job: Job) -> Job: ...

    async def get_by_id(self, job_id: str, organisation_id: str) -> Optional[Job]: ...

    async def update(self, job: Job) -> Job: ...
