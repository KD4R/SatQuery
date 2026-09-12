import json
import logging
import os
from typing import Any, Dict, Optional

import redis as _redis
from celery import Celery

from packages.geo.raster import validate_raster
from packages.geo.crs import normalize_crs
from packages.geo.clipping import clip_raster_to_aoi
from packages.geo.cog import generate_cog
from packages.providers.config import config as provider_config
from services.eo_data.telemetry import tracer, geo_job_duration_ms, inject_context_to_span

logger = logging.getLogger(__name__)

# --- P4-16: Async GeoJob worker ---
celery_app = Celery(
    "geojob_worker",
    broker=provider_config.redis_url.get_secret_value(),
    backend=provider_config.redis_url.get_secret_value(),
)
# In test environments (CELERY_TASK_ALWAYS_EAGER=true), run tasks synchronously.
if os.environ.get("CELERY_TASK_ALWAYS_EAGER", "").lower() == "true":
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

try:
    redis_client = _redis.from_url(
        provider_config.redis_url.get_secret_value(), decode_responses=True
    )
except Exception as _e:
    logger.error(f"Redis initialization failed: {_e}")
    redis_client = None  # type: ignore


@celery_app.task(bind=True, max_retries=3)
def process_geo_job(self, job_id: str, idempotency_key: str, payload: dict, context: dict):
    """
    P4-16: Async GeoJob worker.
    Runs idempotency check then executes the raster pipeline if requested.
    Pipeline: validate_raster → normalize_crs → clip_raster_to_aoi → generate_cog.
    """
    with tracer.start_as_current_span("process_geo_job") as span:
        inject_context_to_span(span, context)

        if not redis_client:
            raise RuntimeError("Redis missing — required for idempotency lock")

        lock_key = f"geojob:idemp:{idempotency_key}"
        if not redis_client.set(lock_key, "processing", nx=True, ex=86400):
            return {"status": "skipped", "reason": "idempotency_key_exists", "job_id": job_id}

        try:
            with geo_job_duration_ms.time():
                # P4-13 / P4-11 / P4-12 raster pipeline (optional — only when payload supplies keys)
                pipeline = payload.get("raster_pipeline")
                if pipeline:
                    source_path: str = pipeline["source_path"]
                    aoi_geojson: Optional[Dict[str, Any]] = pipeline.get("aoi_geojson")
                    output_path: str = pipeline["output_path"]

                    # Step 1 — validate (P4-10)
                    validate_raster(source_path)

                    # Step 2 — CRS normalization to correct UTM zone (P4-11)
                    reprojected_path = source_path.replace(".tif", "_utm.tif")
                    normalize_crs(source_path, reprojected_path)

                    # Step 3 — AOI clipping (P4-12) and PostGIS persistence (P4-14)
                    if aoi_geojson:
                        clipped_path = reprojected_path.replace("_utm.tif", "_clipped.tif")
                        clip_raster_to_aoi(reprojected_path, clipped_path, aoi_geojson)
                        pre_cog_path = clipped_path

                        # Persist AOI
                        from packages.geo.postgis import postgis_ops

                        if postgis_ops:
                            org_id = context.get("organization_id", "default_org")
                            postgis_ops.insert_aoi(org_id, job_id, f"Job {job_id} AOI", aoi_geojson)
                    else:
                        pre_cog_path = reprojected_path

                    # Step 4 — COG with overviews (P4-13)
                    generate_cog(pre_cog_path, output_path)

                    return {"status": "success", "job_id": job_id, "output": output_path}

                # Non-raster job — placeholder for future pipeline shapes
                return {"status": "success", "job_id": job_id}

        except Exception as e:
            redis_client.delete(lock_key)
            span.record_exception(e)
            raise self.retry(exc=e)


# --- P4-17: Geo failure recovery and fixture fallback ---
class FixtureFallbackManager:
    """
    P4-17: Returns pinned deterministic fixtures when live provider calls fail.
    Fixture files live in data/fixtures/ and are loaded by logical name.
    """

    def __init__(self, fixture_dir: str = "data/fixtures"):
        self.fixture_dir = fixture_dir

    def recover_search(self, fallback_id: str, context: dict) -> Dict[str, Any]:
        with tracer.start_as_current_span("recover_fixture") as span:
            inject_context_to_span(span, context)
            fixture_path = os.path.join(self.fixture_dir, f"{fallback_id}.json")
            if not os.path.exists(fixture_path):
                raise FileNotFoundError(f"Fixture not found: {fixture_path}")
            with open(fixture_path, "r") as f:
                return json.load(f)  # type: ignore


fixture_fallback = FixtureFallbackManager()
