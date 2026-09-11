"""
services/mission/repositories/memory.py — In-memory repository implementations.

Used in tests and local development. All operations are O(n) — good enough
for tests; production uses SQLAlchemy implementations with real indexes.

OWASP A01 — Tenant isolation: every read/write filters by organisation_id.
"""

import copy
from typing import Dict, List, Optional

from services.mission.domain.models import AOI, Job, Mission


class InMemoryMissionRepository:
    """Thread-unsafe in-memory store — fine for synchronous test runners."""

    def __init__(self) -> None:
        self._store: Dict[str, Mission] = {}

    async def create(self, mission: Mission) -> Mission:
        self._store[mission.id] = copy.deepcopy(mission)
        return copy.deepcopy(mission)

    async def get_by_id(self, mission_id: str, organisation_id: str) -> Optional[Mission]:
        m = self._store.get(mission_id)
        if m is None or m.organisation_id != organisation_id:
            return None
        return copy.deepcopy(m)

    async def list_by_org(
        self, organisation_id: str, limit: int = 50, offset: int = 0
    ) -> List[Mission]:
        items = [
            copy.deepcopy(m) for m in self._store.values() if m.organisation_id == organisation_id
        ]
        # Stable order: newest first
        items.sort(key=lambda m: m.created_at, reverse=True)
        return items[offset : offset + limit]

    async def count_by_org(self, organisation_id: str) -> int:
        return sum(1 for m in self._store.values() if m.organisation_id == organisation_id)

    async def update(self, mission: Mission) -> Mission:
        self._store[mission.id] = copy.deepcopy(mission)
        return copy.deepcopy(mission)

    async def delete(self, mission_id: str, organisation_id: str) -> bool:
        m = self._store.get(mission_id)
        if m is None or m.organisation_id != organisation_id:
            return False
        del self._store[mission_id]
        return True


class InMemoryAOIRepository:
    def __init__(self) -> None:
        self._store: Dict[str, AOI] = {}

    async def create(self, aoi: AOI) -> AOI:
        self._store[aoi.id] = copy.deepcopy(aoi)
        return copy.deepcopy(aoi)

    async def get_by_id(self, aoi_id: str, organisation_id: str) -> Optional[AOI]:
        a = self._store.get(aoi_id)
        if a is None or a.organisation_id != organisation_id:
            return None
        return copy.deepcopy(a)

    async def list_by_org(
        self, organisation_id: str, limit: int = 50, offset: int = 0
    ) -> List[AOI]:
        items = [
            copy.deepcopy(a) for a in self._store.values() if a.organisation_id == organisation_id
        ]
        items.sort(key=lambda a: a.created_at, reverse=True)
        return items[offset : offset + limit]

    async def count_by_org(self, organisation_id: str) -> int:
        return sum(1 for a in self._store.values() if a.organisation_id == organisation_id)

    async def delete(self, aoi_id: str, organisation_id: str) -> bool:
        a = self._store.get(aoi_id)
        if a is None or a.organisation_id != organisation_id:
            return False
        del self._store[aoi_id]
        return True


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._store: Dict[str, Job] = {}

    async def create(self, job: Job) -> Job:
        self._store[job.id] = copy.deepcopy(job)
        return copy.deepcopy(job)

    async def get_by_id(self, job_id: str, organisation_id: str) -> Optional[Job]:
        j = self._store.get(job_id)
        if j is None or j.organisation_id != organisation_id:
            return None
        return copy.deepcopy(j)

    async def update(self, job: Job) -> Job:
        self._store[job.id] = copy.deepcopy(job)
        return copy.deepcopy(job)
