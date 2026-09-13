import os
from pydantic_settings import BaseSettings


class MissionSettings(BaseSettings):
    # Using sqlite by default for local execution without Docker,
    # but in production this should be postgresql+asyncpg://user:pass@host/db
    database_url: str = os.getenv("MISSION_DATABASE_URL", "sqlite+aiosqlite:///./mission.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    model_config = {"env_file": ".env"}


def get_mission_settings() -> MissionSettings:
    return MissionSettings()
