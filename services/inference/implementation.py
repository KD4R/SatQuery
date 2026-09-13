"""services/inference/implementation.py — the P3 inference FastAPI app (P3-01).

Registers:
  - /api/v1/inference/analyses   run an analysis
  - /api/v1/inference/models     model registry
  - /api/v1/health               liveness

Starts with no model and no torch. Both are optional: with neither, every analysis
runs the deterministic baseline and says so via ``degraded_from``. That is the
point of D7 -- a working answer by a labelled weaker method beats a 503, and it
beats a fabricated one by considerably more.
"""

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from packages.observability import setup_logging
from services.inference.routers.inference import router as inference_router

setup_logging("inference")

app = FastAPI(
    title="SatQuery Inference Service",
    description=(
        "Turns analysis-ready satellite rasters into measurements that carry their "
        "provenance. Every endpoint returns Analysis | Abstention; no code path "
        "fabricates a result."
    ),
    version="1.0.0",
)

app.include_router(inference_router)

_health_router = APIRouter(prefix="/api/v1")


class HealthStatus(BaseModel):
    status: str
    service: str


@_health_router.get("/health", response_model=HealthStatus, tags=["health"])
async def health() -> HealthStatus:
    """Liveness only.

    Deliberately does not check whether a model is loadable. Model availability is
    a degradation, not an outage -- reporting unhealthy would take the service out
    of rotation when it is perfectly able to serve baseline analyses. Ask
    /api/v1/inference/models if you want to know what is loaded.
    """
    return HealthStatus(status="ok", service="inference")


app.include_router(_health_router)
