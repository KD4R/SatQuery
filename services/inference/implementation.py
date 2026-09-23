"""services/inference/implementation.py — the P3 inference FastAPI app (P3-01).

Registers:
  - /api/v1/inference/analyses   run an analysis
  - /api/v1/inference/models     model registry
  - /api/v1/health               liveness

Runs the learned model when it can, and the deterministic baseline when it cannot.
With torch installed and a verified checkpoint under SATQUERY_MODEL_ROOT, every
analysis is produced by the model and names it in ``produced_by``. Without either,
analyses run the baseline and say so via ``degraded_from`` -- D7: a working answer
by a labelled weaker method beats a 503, and beats a fabricated one by more.

The default model is loaded at startup (``lifespan`` below) rather than on the
first request. Two reasons: the first analyst should not pay a load, and a
checkpoint that fails its checksum or will not deserialise should show up in the
boot log, not as a silent degradation on whichever request happens to come first.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from packages.observability import setup_logging
from services.inference.dependencies import get_registry
from services.inference.registry import ModelRegistry, ModelUnavailable
from services.inference.routers.inference import router as inference_router

setup_logging("inference")
logger = logging.getLogger(__name__)


async def warm_default_model() -> str | None:
    """Load, verify and cache the default model. Never raises.

    Returns the name warmed, or None. A failure here is logged and swallowed: the
    service must still come up and serve baseline analyses, which is the whole
    reason the fallback exists. Torch's load is blocking, so it runs off the event
    loop.
    """
    # Resolved through the same override table FastAPI uses, so the registry that
    # is warmed is the one the endpoints will be handed. Calling get_registry()
    # directly would sidestep dependency_overrides and warm a different object.
    registry: ModelRegistry = app.dependency_overrides.get(get_registry, get_registry)()
    name = registry.default()
    if name is None:
        logger.info("no model beats the baseline on held-out regions; serving the baseline")
        return None
    try:
        await asyncio.to_thread(registry.load, name)
    except ModelUnavailable as error:
        logger.warning(
            "default model %s could not be loaded; analyses will degrade: %s", name, error
        )
        return None
    logger.info("model %s loaded and verified at startup", name)
    return name


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await warm_default_model()
    yield


app = FastAPI(
    title="SatQuery Inference Service",
    description=(
        "Turns analysis-ready satellite rasters into measurements that carry their "
        "provenance. Every endpoint returns Analysis | Abstention; no code path "
        "fabricates a result."
    ),
    version="1.0.0",
    lifespan=lifespan,
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
