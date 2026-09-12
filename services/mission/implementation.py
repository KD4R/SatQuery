"""
services/mission/implementation.py — Mission FastAPI application (P1-06, P1-07).

Registers all Mission service routers:
  - /api/v1/missions   (CRUD)
  - /api/v1/aois       (CRUD)
  - /api/v1/missions/{id}/runs  (job submission)
  - /api/v1/jobs/{id}           (job status polling)
"""

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from packages.observability import setup_logging, setup_telemetry
from packages.shared.middleware import IdempotencyMiddleware
from services.mission.routers.agents import router as agents_router
from services.mission.routers.aois import router as aois_router
from services.mission.routers.jobs import router as jobs_router
from services.mission.routers.missions import router as missions_router

setup_logging("mission")

app = FastAPI(
    title="SatQuery Mission Service",
    description="Mission and AOI lifecycle management for SatQuery AI",
    version="1.0.0",
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
