import logging
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis

from packages.providers.config import config
from packages.providers.bhoonidhi import BhoonidhiAdapter
from packages.providers.stac import STACProvider
from services.eo_data.normalization import normalize_pipeline
from packages.contracts import Observation

logger = logging.getLogger(__name__)

# Initialize robust connection mapped properly
redis_client = redis.from_url(config.redis_url.get_secret_value(), decode_responses=True)


class SearchService:
    """
    Implements P4-07 Spatial/Temporal Observation Search.
    Utilizes local STAC mirror caching to achieve <2s NFR target.
    Gracefully degrades to live fetch if cache infrastructure drops.
    """

    def __init__(self):
        self.bhoonidhi = BhoonidhiAdapter()
        self.planetary_computer = STACProvider(
            "planetary_computer", "https://planetarycomputer.microsoft.com/api/stac/v1"
        )
        self.CACHE_TTL = 3600  # 1 hr cache for metadata searches

    def _generate_cache_key(
        self, provider_name: str, polygon: Dict, start: datetime, end: datetime, **kwargs
    ) -> str:
        payload = {
            "provider": provider_name,
            "polygon": polygon,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "kwargs": kwargs,
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return f"stac:mirror:{hashlib.md5(payload_bytes, usedforsecurity=False).hexdigest()}"

    def search_observations(
        self,
        polygon: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        context: dict | None = None,
        cloud_cover: float = 100.0,
        provider_name: str = "bhoonidhi",
        **kwargs,
    ) -> List[Observation]:
        from services.eo_data.telemetry import tracer, inject_context_to_span, geo_search_latency_ms

        with tracer.start_as_current_span("search_observations") as span:
            inject_context_to_span(span, context or {})
            with geo_search_latency_ms.time():
                cache_key = self._generate_cache_key(
                    provider_name, polygon, start_date, end_date, cloud_cover=cloud_cover, **kwargs
                )

                try:
                    cached_data = redis_client.get(cache_key) if redis_client else None
                    if cached_data:
                        logger.info("Serving metadata search from STAC mirror cache")
                        raw_items = json.loads(cached_data)
                        return [Observation.model_validate(obs) for obs in raw_items]
                except redis.RedisError as e:
                    logger.warning(
                        f"Redis cache unavailable, falling back to direct fetch. Error: {e}"
                    )
                    cached_data = None

                logger.info(f"Cache miss or bypassed. Fetching from provider: {provider_name}")
                if provider_name == "bhoonidhi":
                    raw_items = self.bhoonidhi.search(
                        polygon, start_date, end_date, cloud_cover, context=context, **kwargs
                    )
                elif provider_name == "planetary_computer":
                    raw_items = self.planetary_computer.search(
                        polygon, start_date, end_date, cloud_cover, **kwargs
                    )
                else:
                    raise ValueError(f"Unknown provider: {provider_name}")

                observations = normalize_pipeline(provider_name, raw_items)

                # P4 Data Quality Intelligence: Report rejection back to the agent
                if raw_items and not observations:
                    raise ValueError(
                        "All discovered STAC assets were rejected due to poor Data Quality "
                        "Intelligence (excessive cloud cover, missing bands, or poor geometry). "
                        "Please search for a different date range."
                    )

                if observations and redis_client:
                    try:
                        dumped = [obs.model_dump(mode="json") for obs in observations]
                        redis_client.setex(cache_key, self.CACHE_TTL, json.dumps(dumped))
                    except redis.RedisError as e:
                        logger.warning(f"Failed to write to Redis cache: {e}")

                return observations  # type: ignore

    def get_latest_cloud_free_observation(
        self,
        polygon: Dict[str, Any],
        context: dict,
        max_cloud_cover: float = 10.0,
        provider_name: str = "bhoonidhi",
    ) -> Optional[Observation]:
        """P4-18: Return the most recent observation below cloud cover threshold."""
        observations = self.search_observations(
            polygon, datetime.now(), datetime.now(), context, provider_name=provider_name
        )
        clear = [o for o in observations if (o.scene.cloud_cover or 0) < max_cloud_cover]
        return clear[0] if clear else None


search_service = SearchService()
