"""Dependency wiring for the inference service.

Kept in one place so tests can override any piece with
``app.dependency_overrides`` -- the registry to point at a temporary directory,
the raster source to point at fixture chips -- without touching the router or
reaching for monkeypatching. The service is then exercised through the real HTTP
stack, which is the only way to catch a serialisation or auth defect.

``lru_cache`` on the registry because loading a checkpoint costs a second and
model weights are immutable once written; a per-request registry would reload the
same file on every call.
"""

from __future__ import annotations

from functools import lru_cache

from services.inference.registry import ModelRegistry
from services.inference.service import AnalysisService
from services.inference.sources import LocalRasterSource, RasterSource

#: Version recorded in every Measurement this service produces. Bumped when the
#: analysis path changes in a way that could move a number -- it is what lets a
#: figure quoted in a report be traced back to the code that produced it.
CODE_VERSION = "0.2.0"


@lru_cache(maxsize=1)
def get_registry() -> ModelRegistry:
    return ModelRegistry()


@lru_cache(maxsize=1)
def get_raster_source() -> RasterSource:
    return LocalRasterSource()


def get_analysis_service() -> AnalysisService:
    return AnalysisService(
        registry=get_registry(),
        source=get_raster_source(),
        code_version=CODE_VERSION,
    )
