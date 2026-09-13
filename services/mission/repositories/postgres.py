from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from services.mission.domain.models import Mission, AOI, Job
from services.mission.domain.db_models import MissionModel, AOIModel, JobModel
from services.mission.repositories.base import MissionRepository, AOIRepository, JobRepository


class PostgresMissionRepository(MissionRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_domain(self, model: MissionModel) -> Mission:
        return Mission(
            id=model.id,
            name=model.name,
            description=model.description,
            status=model.status,
            aoi_ids=model.aoi_ids,
            organisation_id=model.organisation_id,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create(self, mission: Mission) -> Mission:
        model = MissionModel(
            id=mission.id,
            name=mission.name,
            description=mission.description,
            status=mission.status,
            aoi_ids=mission.aoi_ids,
            organisation_id=mission.organisation_id,
            created_by=mission.created_by,
            created_at=mission.created_at,
            updated_at=mission.updated_at,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def get_by_id(self, mission_id: str, organisation_id: str) -> Optional[Mission]:
        stmt = select(MissionModel).where(
            MissionModel.id == mission_id, MissionModel.organisation_id == organisation_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def list_by_org(
        self, organisation_id: str, limit: int = 50, offset: int = 0
    ) -> List[Mission]:
        stmt = (
            select(MissionModel)
            .where(MissionModel.organisation_id == organisation_id)
            .order_by(MissionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_by_org(self, organisation_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(MissionModel)
            .where(MissionModel.organisation_id == organisation_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update(self, mission: Mission) -> Mission:
        stmt = select(MissionModel).where(
            MissionModel.id == mission.id, MissionModel.organisation_id == mission.organisation_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one()
        model.name = mission.name
        model.description = mission.description
        model.status = mission.status
        model.aoi_ids = mission.aoi_ids
        model.updated_at = mission.updated_at
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def delete(self, mission_id: str, organisation_id: str) -> bool:
        stmt = select(MissionModel).where(
            MissionModel.id == mission_id, MissionModel.organisation_id == organisation_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True


class PostgresAOIRepository(AOIRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_domain(self, model: AOIModel) -> AOI:
        return AOI(
            id=model.id,
            name=model.name,
            description=model.description,
            geometry=model.geometry,
            organisation_id=model.organisation_id,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create(self, aoi: AOI) -> AOI:
        model = AOIModel(
            id=aoi.id,
            name=aoi.name,
            description=aoi.description,
            geometry=aoi.geometry,
            organisation_id=aoi.organisation_id,
            created_by=aoi.created_by,
            created_at=aoi.created_at,
            updated_at=aoi.updated_at,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def get_by_id(self, aoi_id: str, organisation_id: str) -> Optional[AOI]:
        stmt = select(AOIModel).where(
            AOIModel.id == aoi_id, AOIModel.organisation_id == organisation_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def list_by_org(
        self, organisation_id: str, limit: int = 50, offset: int = 0
    ) -> List[AOI]:
        stmt = (
            select(AOIModel)
            .where(AOIModel.organisation_id == organisation_id)
            .order_by(AOIModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return [self._to_domain(a) for a in result.scalars().all()]

    async def count_by_org(self, organisation_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(AOIModel)
            .where(AOIModel.organisation_id == organisation_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete(self, aoi_id: str, organisation_id: str) -> bool:
        stmt = select(AOIModel).where(
            AOIModel.id == aoi_id, AOIModel.organisation_id == organisation_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.session.delete(model)
        await self.session.commit()
        return True


class PostgresJobRepository(JobRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_domain(self, model: JobModel) -> Job:
        return Job(
            id=model.id,
            mission_id=model.mission_id,
            status=model.status,
            organisation_id=model.organisation_id,
            submitted_by=model.submitted_by,
            submitted_at=model.submitted_at,
            started_at=model.started_at,
            completed_at=model.completed_at,
            trace_id=model.trace_id,
            error_message=model.error_message,
        )

    async def create(self, job: Job) -> Job:
        model = JobModel(
            id=job.id,
            mission_id=job.mission_id,
            status=job.status,
            organisation_id=job.organisation_id,
            submitted_by=job.submitted_by,
            submitted_at=job.submitted_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            trace_id=job.trace_id,
            error_message=job.error_message,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)

    async def get_by_id(self, job_id: str, organisation_id: str) -> Optional[Job]:
        stmt = select(JobModel).where(
            JobModel.id == job_id, JobModel.organisation_id == organisation_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_domain(model)

    async def update(self, job: Job) -> Job:
        stmt = select(JobModel).where(
            JobModel.id == job.id, JobModel.organisation_id == job.organisation_id
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one()
        model.status = job.status
        model.started_at = job.started_at
        model.completed_at = job.completed_at
        model.trace_id = job.trace_id
        model.error_message = job.error_message
        await self.session.commit()
        await self.session.refresh(model)
        return self._to_domain(model)
