import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from services.mission.config import get_mission_settings

logger = logging.getLogger(__name__)
settings = get_mission_settings()

engine = create_async_engine(
    settings.database_url, 
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        # For simplicity in local testing, we create all tables automatically.
        # In production, Alembic migrations should be used.
        await conn.run_sync(Base.metadata.create_all)
