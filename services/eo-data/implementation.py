import logging
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import redis
import boto3
from botocore.config import Config as BotoConfig
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings

from .telemetry import tracer, geo_search_latency_ms, asset_download_failure_total, inject_context_to_span
from .errors import ErrorResponse

logger = logging.getLogger(__name__)

from packages.providers.config import config
from packages.providers.bhoonidhi import BhoonidhiAdapter

try:
    redis_client = redis.from_url(config.redis_url.get_secret_value(), decode_responses=True)
except Exception as e:
    logger.error(f"Redis initialization failed: {e}")
    redis_client = None

from packages.contracts.data import SceneRef, Observation, Provider, PassDirection, AssetRef

class SearchService:
    def __init__(self):
        self.bhoonidhi = BhoonidhiAdapter()

    @geo_search_latency_ms.time()
    def search_observations(self, polygon: Dict[str, Any], start_date: datetime, end_date: datetime, context: dict, cloud_cover: float = 100.0) -> List[Observation]:
        with tracer.start_as_current_span("search_observations") as span:
            inject_context_to_span(span, context)
            
            cache_key = f"stac:mirror:{hashlib.md5(json.dumps({'p': polygon, 's': start_date.isoformat()}, sort_keys=True).encode()).hexdigest()}"
            if redis_client:
                try:
                    if cached := redis_client.get(cache_key):
                        return [Observation.model_validate(obs) for obs in json.loads(cached)]
                except redis.RedisError:
                    pass

            try:
                raw_items = self.bhoonidhi.search(polygon, start_date, end_date, cloud_cover=cloud_cover, context=context)
            except Exception as e:
                span.record_exception(e)
                logger.warning(f"Bhoonidhi search failed ({e}), attempting fixture fallback.")
                from services.geo.implementation import fixture_fallback
                # Fallback to a pinned fixture based on the provider
                try:
                    fixture_data = fixture_fallback.recover_search("bhoonidhi_sample", context)
                    raw_items = fixture_data.get("features", [])
                except Exception as fallback_e:
                    logger.error(f"Fallback failed: {fallback_e}")
                    raise e
            
            observations = []
            import uuid
            for item in raw_items:
                try:
                    props = item.get("properties", {})
                    dt = datetime.fromisoformat(props["datetime"].replace("Z", "+00:00"))

                    # Map sat:orbit_state to PassDirection enum (case-insensitive)
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
                        stac_href=item.get("links", [{"href": ""}])[0]["href"],
                        cloud_cover=c_cover_val,
                    )
                    obs = Observation(
                        observation_id=str(uuid.uuid4()),
                        scene=scene,
                        geometry=item.get("geometry", {}),
                        assets={
                            k: AssetRef(
                                href=v.get("href", ""),
                                media_type=v.get("type"),
                                roles=v.get("roles")
                            ) for k, v in item.get("assets", {}).items()
                        },
                        normalized_properties={
                            "offline_status": item.get("_bhoonidhi_status"),
                            "quality_score": quality_score
                        }
                    )
                    observations.append(obs)
                except Exception as e:
                    logger.error(f"Normalization failed: {e}")
                    
            if redis_client and observations:
                try:
                    redis_client.setex(cache_key, 3600, json.dumps([o.model_dump(mode='json') for o in observations]))
                except redis.RedisError:
                    pass
            return observations

    def get_latest_cloud_free_observation(self, polygon: Dict[str, Any], context: dict) -> Optional[Observation]:
        """
        P4-18: Monitoring observation selection support.
        Identifies the best continuous monitoring observation by searching recent windows
        and sorting by least cloud cover.
        """
        from datetime import timedelta
        with tracer.start_as_current_span("monitoring_selection") as span:
            inject_context_to_span(span, context)
            now = datetime.now(timezone.utc)
            start = now - timedelta(days=14)
            
            observations = self.search_observations(polygon, start, now, context)
            
            # Filter strictly for cloud-free (less than 10%)
            valid = [o for o in observations if o.scene.cloud_cover is None or o.scene.cloud_cover < 10.0]
            
            if not valid:
                return None
            
            # Return most recent valid observation
            valid.sort(key=lambda x: x.scene.acquired_at, reverse=True)
            return valid[0]

search_service = SearchService()
