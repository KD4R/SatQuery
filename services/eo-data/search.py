import logging
import json
import hashlib
from typing import Dict, Any, List
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
        provider_name: str,
        polygon: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        cloud_cover: float = 100.0,
        **kwargs,
    ) -> List[Observation]:

        cache_key = self._generate_cache_key(
            provider_name, polygon, start_date, end_date, cloud_cover=cloud_cover, **kwargs
        )

        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info("Serving metadata search from STAC mirror cache")
                raw_items = json.loads(cached_data)
                return [Observation.model_validate(obs) for obs in raw_items]
        except redis.RedisError as e:
            logger.warning(f"Redis cache unavailable, falling back to direct fetch. Error: {e}")
            cached_data = None

        logger.info(f"Cache miss or bypassed. Fetching from provider: {provider_name}")
        if provider_name == "bhoonidhi":
            raw_items = self.bhoonidhi.search(polygon, start_date, end_date, cloud_cover, **kwargs)
        elif provider_name == "planetary_computer":
            raw_items = self.planetary_computer.search(
                polygon, start_date, end_date, cloud_cover, **kwargs
            )
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

        observations = normalize_pipeline(provider_name, raw_items)

        if observations:
            try:
                dumped = [obs.model_dump(mode="json") for obs in observations]
                redis_client.setex(cache_key, self.CACHE_TTL, json.dumps(dumped))
            except redis.RedisError as e:
                logger.warning(f"Failed to write to Redis cache: {e}")

        return observations  # type: ignore


search_service = SearchService()
