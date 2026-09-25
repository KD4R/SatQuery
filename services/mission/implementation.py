"""
services/mission/implementation.py — Mission FastAPI application (P1-06, P1-07).

Registers all Mission service routers:
  - /api/v1/missions   (CRUD)
  - /api/v1/aois       (CRUD)
  - /api/v1/missions/{id}/runs  (job submission)
  - /api/v1/jobs/{id}           (job status polling)
"""

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from packages.observability import setup_logging, setup_telemetry
from packages.shared.middleware import IdempotencyMiddleware
from services.mission.database import init_db
# Import model declarations so Base.metadata contains the Mission/AOI/Job tables
# before the local Compose startup initializer runs.
from services.mission.domain import db_models as _db_models  # noqa: F401
from services.mission.routers.agents import router as agents_router
from services.mission.routers.aois import router as aois_router
from services.mission.routers.jobs import router as jobs_router
from services.mission.routers.missions import router as missions_router

setup_logging("mission")

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the local runtime schema before serving mission requests.

    Production deployments should run versioned migrations before startup. The
    current Compose release profile has no migration container, so creating
    missing tables here is required for a clean local/integration environment.
    Tests set SATQUERY_SKIP_DB_INIT and inject in-memory repositories.
    """
    if os.getenv("SATQUERY_SKIP_DB_INIT", "false").lower() != "true":
        await init_db()
    yield


app = FastAPI(
    title="SatQuery Mission Service",
    description="Mission and AOI lifecycle management for SatQuery AI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(IdempotencyMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(missions_router)
app.include_router(aois_router)
app.include_router(jobs_router)
app.include_router(agents_router)

_health_router = APIRouter(prefix="/api/v1")


class HealthStatus(BaseModel):
    status: str
    service: str


@_health_router.get("/health", response_model=HealthStatus)
async def health_check():
    return HealthStatus(status="ok", service="mission")


app.include_router(_health_router)
setup_telemetry(app, "mission")
