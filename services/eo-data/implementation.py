import logging
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import redis
from redis.exceptions import LockError
import boto3
from botocore.config import Config as BotoConfig
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings

from .telemetry import tracer, geo_search_latency_ms, asset_download_failure_total, inject_context_to_span
from .errors import ErrorResponse

logger = logging.getLogger(__name__)

class ProviderConfig(BaseSettings):
    bhoonidhi_username: SecretStr = Field(default=SecretStr(""), alias="BHOONIDHI_USERNAME")
    bhoonidhi_password: SecretStr = Field(default=SecretStr(""), alias="BHOONIDHI_PASSWORD")
    bhoonidhi_api_url: str = Field(default="https://bhoonidhi-api.nrsc.gov.in", alias="BHOONIDHI_API_URL")
    redis_url: SecretStr = Field(default=SecretStr("redis://localhost:6379/0"), alias="REDIS_URL")
    s3_endpoint: str = Field(default="s3.amazonaws.com", alias="S3_ENDPOINT")
    s3_access_key: SecretStr = Field(default=SecretStr(""), alias="S3_ACCESS_KEY")
    s3_secret_key: SecretStr = Field(default=SecretStr(""), alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="satquery-assets", alias="S3_BUCKET")
    request_timeout_sec: float = Field(default=15.0, alias="REQUEST_TIMEOUT_SEC")
    
    class Config:
        env_file = ".env"

config = ProviderConfig()

try:
    redis_client = redis.from_url(config.redis_url.get_secret_value(), decode_responses=True)
except Exception as e:
    logger.error(f"Redis initialization failed: {e}")
    redis_client = None

class SceneRef(BaseModel):
    provider: str
    collection: str
    item_id: str
    acquired_at: datetime
    platform: str
    instrument: str
    relative_orbit: Optional[int] = None
    pass_direction: Optional[str] = None
    stac_href: str
    cloud_cover: Optional[float] = None

class Observation(BaseModel):
    observation_id: str
    scene: SceneRef
    geometry: Dict[str, Any]
    assets: Dict[str, str]
    normalized_properties: Dict[str, Any] = Field(default_factory=dict)

class BhoonidhiAdapter:
    def __init__(self):
        self.base_url = config.bhoonidhi_api_url.rstrip("/")
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"https://{config.s3_endpoint}",
            aws_access_key_id=config.s3_access_key.get_secret_value(),
            aws_secret_access_key=config.s3_secret_key.get_secret_value(),
            config=BotoConfig(retries={'max_attempts': 3})
        )

    def _get_auth_token(self, context: dict) -> str:
        with tracer.start_as_current_span("bhoonidhi_auth") as span:
            inject_context_to_span(span, context)
            if not redis_client:
                raise RuntimeError("Redis required for distributed Bhoonidhi auth limits")
                
            token = redis_client.get("bhoonidhi:auth:token")
            if token:
                return token
                
            try:
                with redis_client.lock("bhoonidhi:auth:lock", timeout=15, blocking_timeout=10):
                    token = redis_client.get("bhoonidhi:auth:token")
                    if token: return token
                    
                    auth_count = redis_client.get("bhoonidhi:auth:budget") or 0
                    if int(auth_count) >= 20:
                        raise RuntimeError("Bhoonidhi 20 auths/hr budget exceeded.")
                        
                    resp = self.session.post(
                        f"{self.base_url}/auth/token",
                        json={
                            "username": config.bhoonidhi_username.get_secret_value(),
                            "password": config.bhoonidhi_password.get_secret_value()
                        },
                        timeout=config.request_timeout_sec
                    )
                    resp.raise_for_status()
                    new_token = resp.json().get("access_token")
                    
                    redis_client.setex("bhoonidhi:auth:token", 960, new_token)
                    pipe = redis_client.pipeline()
                    pipe.incr("bhoonidhi:auth:budget")
                    if int(auth_count) == 0:
                        pipe.expire("bhoonidhi:auth:budget", 3600)
                    pipe.execute()
                    
                    return new_token
            except Exception as e:
                span.record_exception(e)
                raise RuntimeError(f"Auth failure: {e}")

    def search(self, polygon: Dict[str, Any], start_date: datetime, end_date: datetime, context: dict) -> List[Dict[str, Any]]:
        with tracer.start_as_current_span("bhoonidhi_search") as span:
            inject_context_to_span(span, context)
            token = self._get_auth_token(context)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {
                "filter-lang": "cql2-json",
                "filter": {
                    "op": "and",
                    "args": [
                        {"op": "s_intersects", "args": [{"property": "geometry"}, polygon]},
                        {"op": "t_intersects", "args": [{"property": "datetime"}, [start_date.isoformat() + "Z", end_date.isoformat() + "Z"]]}
                    ]
                }
            }
            resp = self.session.post(f"{self.base_url}/data/search", headers=headers, json=payload, timeout=config.request_timeout_sec)
            resp.raise_for_status()
            
            features = resp.json().get("features", [])
            for f in features:
                if f.get("properties", {}).get("Online") == "N":
                    f["_bhoonidhi_status"] = "PRODUCT_OFFLINE"
            return features

    def get_asset(self, item_id: str, asset_key: str, context: dict) -> str:
        with tracer.start_as_current_span("bhoonidhi_download") as span:
            inject_context_to_span(span, context)
            token = self._get_auth_token(context)
            download_url = f"{self.base_url}/data/download/{item_id}_{asset_key}.tif"
            s3_key = f"assets/{item_id}/{asset_key}.tif"
            try:
                with self.session.get(download_url, headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=(5.0, 60.0)) as r:
                    r.raise_for_status()
                    self.s3_client.upload_fileobj(r.raw, config.s3_bucket, s3_key, ExtraArgs={"ContentType": "image/tiff"})
                return f"s3://{config.s3_bucket}/{s3_key}"
            except Exception as e:
                asset_download_failure_total.inc()
                span.record_exception(e)
                raise RuntimeError(f"Asset download failed: {e}")

class SearchService:
    def __init__(self):
        self.bhoonidhi = BhoonidhiAdapter()

    @geo_search_latency_ms.time()
    def search_observations(self, polygon: Dict[str, Any], start_date: datetime, end_date: datetime, context: dict) -> List[Observation]:
        with tracer.start_as_current_span("search_observations") as span:
            inject_context_to_span(span, context)
            
            cache_key = f"stac:mirror:{hashlib.md5(json.dumps({'p': polygon, 's': start_date.isoformat()}, sort_keys=True).encode()).hexdigest()}"
            if redis_client:
                try:
                    if cached := redis_client.get(cache_key):
                        return [Observation.model_validate(obs) for obs in json.loads(cached)]
                except redis.RedisError:
                    pass

            raw_items = self.bhoonidhi.search(polygon, start_date, end_date, context)
            
            observations = []
            import uuid
            for item in raw_items:
                try:
                    dt = datetime.fromisoformat(item["properties"]["datetime"].replace("Z", "+00:00"))
                    scene = SceneRef(
                        provider="bhoonidhi",
                        collection=item.get("collection", "Unknown"),
                        item_id=item.get("id", "Unknown"),
                        acquired_at=dt,
                        platform=item["properties"].get("platform", "Unknown"),
                        instrument=item["properties"].get("instruments", ["Unknown"])[0],
                        stac_href=item.get("links", [{"href":""}])[0]["href"]
                    )
                    obs = Observation(
                        observation_id=str(uuid.uuid4()),
                        scene=scene,
                        geometry=item.get("geometry", {}),
                        assets={k: v.get("href", "") for k, v in item.get("assets", {}).items()},
                        normalized_properties={"offline_status": item.get("_bhoonidhi_status")}
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

search_service = SearchService()
