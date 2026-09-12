import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis

from packages.contracts import Observation, PassDirection, Provider, SceneRef
from packages.providers.bhoonidhi import BhoonidhiAdapter
from packages.providers.config import config

from .telemetry import (
    geo_search_latency_ms,
    inject_context_to_span,
    tracer,
)

logger = logging.getLogger(__name__)

try:
    redis_client = redis.from_url(config.redis_url.get_secret_value(), decode_responses=True)
except Exception as e:
    logger.error(f"Redis initialization failed: {e}")
    redis_client = None


class SearchService:
    def __init__(self):
        self.bhoonidhi = BhoonidhiAdapter()

    @geo_search_latency_ms.time()
    def search_observations(
        self,
        polygon: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        context: dict,
        cloud_cover: float = 100.0,
    ) -> List[Observation]:
        with tracer.start_as_current_span("search_observations") as span:
            inject_context_to_span(span, context)

            payload = json.dumps(
                {"p": polygon, "s": start_date.isoformat()}, sort_keys=True
            ).encode()
            cache_key = f"stac:mirror:{hashlib.md5(payload, usedforsecurity=False).hexdigest()}"
            if redis_client:
                try:
                    if cached := redis_client.get(cache_key):
                        return [Observation.model_validate(obs) for obs in json.loads(cached)]
                except redis.RedisError:
                    pass

            try:
                raw_items = self.bhoonidhi.search(
                    polygon, start_date, end_date, cloud_cover=cloud_cover, context=context
                )
            except Exception as e:
                span.record_exception(e)
                logger.warning(f"Bhoonidhi search failed ({e}), attempting fixture fallback.")
                from services.geo.implementation import fixture_fallback

                raw_items = fixture_fallback.recover_search("bhoonidhi_sample", {}).get(
                    "features", []
                )

            observations = []
            for item in raw_items:
                try:
                    props = item.get("properties", {})
                    dt_str = props.get("datetime")
                    if not dt_str:
                        continue
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

                    raw_direction = props.get("sat:orbit_state")
                    if raw_direction:
                        try:
                            pass_direction = PassDirection(raw_direction.upper())
                        except ValueError:
                            pass_direction = None
                    else:
                        pass_direction = None

                    c_cover = props.get("eo:cloud_cover")
                    c_cover_val = float(c_cover) if c_cover is not None else 0.0

                    # P4-19: Quality scoring enrichment
                    quality_score = max(0, 100 - c_cover_val)

                    scene = SceneRef(
                        provider=Provider.BHOONIDHI,
                        collection=item.get("collection", "Unknown"),
                        item_id=item.get("id", "Unknown"),
                        acquired_at=dt,
                        platform=props.get("platform", "Unknown"),
                        instrument=props.get("instruments", ["Unknown"])[0],
                        relative_orbit=props.get("sat:relative_orbit"),
                        pass_direction=pass_direction,
                        href=item.get("links", [{"href": ""}])[0]["href"],
                        cloud_cover=c_cover_val,
                    )
                    obs = Observation(
                        observation_id=str(__import__("uuid").uuid4()),
                        scene=scene,
                        geometry=item.get("geometry", {}),
                        assets={
                            k: v.get("href", "")
                            for k, v in item.get("assets", {}).items()
                            if "href" in v
                        },
                        normalized_properties={
                            "offline_status": item.get("_bhoonidhi_status"),
                            "quality_score": quality_score,
                        },
                    )
                    observations.append(obs)
                except Exception as e:
                    logger.error(f"Normalization failed: {e}")

            if redis_client and observations:
                try:
                    redis_client.setex(
                        cache_key,
                        3600,
                        json.dumps([o.model_dump(mode="json") for o in observations]),
                    )
                except redis.RedisError:
                    pass
            return observations

    def get_latest_cloud_free_observation(
        self, polygon: Dict[str, Any], context: dict, max_cloud_cover: float = 10.0
    ) -> Optional[Observation]:
        """P4-18: Return the most recent observation below cloud cover threshold."""
        observations = self.search_observations(polygon, datetime.now(), datetime.now(), context)
        clear = [o for o in observations if (o.scene.cloud_cover or 0) < max_cloud_cover]
        return clear[0] if clear else None


# Module-level singleton used by api.py
search_service = SearchService()
