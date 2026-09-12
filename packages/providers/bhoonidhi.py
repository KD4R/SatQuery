import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import redis
from redis.exceptions import LockError
import boto3
from botocore.config import Config as BotoConfig

from packages.providers.base import AbstractProvider
from packages.providers.config import config

logger = logging.getLogger(__name__)

# Distributed constants based on NFRs
BHOONIDHI_TOKEN_KEY = "bhoonidhi:auth:token"
BHOONIDHI_LOCK_KEY = "bhoonidhi:auth:lock"
TOKEN_TTL_SECONDS = 16 * 60  # Cache for ~16 mins (Token expires in 20 mins)
AUTH_BUDGET_KEY = "bhoonidhi:auth:budget"  # To enforce 20 auths/hr


class BhoonidhiAdapter(AbstractProvider):
    """
    Bhoonidhi specific adapter handling strict rate limits and auth constraints.
    - Max 20 auths/hr per IP (Distributed lock via Redis)
    - Max 3 concurrent downloads
    """

    def __init__(self):
        self.name = "bhoonidhi"
        self.base_url = config.bhoonidhi_api_url.rstrip("/")
        self.redis_client = redis.from_url(
            config.redis_url.get_secret_value(), decode_responses=True
        )
        self.timeout = config.request_timeout_sec

        # Setup resilient requests session
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

        # Setup S3 client for asset staging
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=f"https://{config.s3_endpoint}",
            aws_access_key_id=config.s3_access_key.get_secret_value(),
            aws_secret_access_key=config.s3_secret_key.get_secret_value(),
            config=BotoConfig(retries={"max_attempts": 3}),
        )

    def _get_auth_token(self, context: dict = None) -> str:
        """
        Fetch valid token from Redis or authenticate ensuring 20 auth/hr limit.
        """
        from services.eo_data.telemetry import tracer, inject_context_to_span

        context = context or {}
        with tracer.start_as_current_span("bhoonidhi_auth") as span:
            inject_context_to_span(span, context)

            token = self.redis_client.get(BHOONIDHI_TOKEN_KEY)
            if token:
                return token

            # Token missing, acquire lock to refresh
            try:
                with self.redis_client.lock(BHOONIDHI_LOCK_KEY, timeout=15, blocking_timeout=10):
                    # Double-check inside lock
                    token = self.redis_client.get(BHOONIDHI_TOKEN_KEY)
                    if token:
                        return token

                    # Enforce 20 auths/hr budget
                    auth_count = self.redis_client.get(AUTH_BUDGET_KEY) or 0
                    if int(auth_count) >= 20:
                        raise RuntimeError("Bhoonidhi 20 auths/hr budget exceeded. Abstaining.")

                    logger.info("Authenticating with Bhoonidhi...")
                    resp = self.session.post(
                        f"{self.base_url}/auth/token",
                        json={
                            "username": config.bhoonidhi_username.get_secret_value(),
                            "password": config.bhoonidhi_password.get_secret_value(),
                        },
                        timeout=self.timeout,
                    )
                    resp.raise_for_status()

                    resp_json = resp.json()
                    new_token = resp_json.get("access_token")
                    if not new_token:
                        raise ValueError("Auth response missing access_token")

                    # Cache token and increment budget
                    self.redis_client.setex(BHOONIDHI_TOKEN_KEY, TOKEN_TTL_SECONDS, new_token)

                    # Increment hourly budget counter (expire in 1 hr if it's the first)
                    pipe = self.redis_client.pipeline()
                    pipe.incr(AUTH_BUDGET_KEY)
                    if int(auth_count) == 0:
                        pipe.expire(AUTH_BUDGET_KEY, 3600)
                    pipe.execute()

                    return new_token

            except LockError:
                raise RuntimeError(
                    "Failed to acquire auth lock. Another worker might be authenticating."
                )
            except requests.RequestException as e:
                span.record_exception(e)
                logger.error(f"Bhoonidhi authentication network failure: {e}")
                raise

    def search(
        self,
        polygon: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        cloud_cover: float = 100.0,
        context: dict = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Search Bhoonidhi STAC catalog utilizing CQL2 filters.
        """
        from services.eo_data.telemetry import tracer, inject_context_to_span

        context = context or {}
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
                        {
                            "op": "t_intersects",
                            "args": [
                                {"property": "datetime"},
                                [start_date.isoformat() + "Z", end_date.isoformat() + "Z"],
                            ],
                        },
                        {"op": "<=", "args": [{"property": "eo:cloud_cover"}, cloud_cover]},
                    ],
                },
            }

            resp = self.session.post(
                f"{self.base_url}/data/search", headers=headers, json=payload, timeout=self.timeout
            )
            resp.raise_for_status()

            features = resp.json().get("features", [])

            # Apply Online/Offline constraint tagging (Browse & Order)
            for feature in features:
                if feature.get("properties", {}).get("Online") == "N":
                    feature["_bhoonidhi_status"] = "PRODUCT_OFFLINE"

            return features

    def get_asset(self, item_id: str, asset_key: str, context: dict = None) -> Optional[str]:
        """
        Streams the asset from Bhoonidhi into S3/MinIO and returns the S3 URI.
        Requires auth token. Network timeouts heavily padded for large assets.
        """
        from services.eo_data.telemetry import (
            tracer,
            inject_context_to_span,
            asset_download_failure_total,
        )
        from packages.geo.validation import validate_asset_href

        context = context or {}
        with tracer.start_as_current_span("bhoonidhi_download") as span:
            inject_context_to_span(span, context)
            token = self._get_auth_token(context)
            headers = {"Authorization": f"Bearer {token}"}

            download_url = f"{self.base_url}/data/download/{item_id}_{asset_key}.tif"

            # P4-09: Secure asset retrieval
            validate_asset_href(download_url)

            s3_key = f"assets/{item_id}/{asset_key}.tif"

            try:
                # We enforce max 3 concurrent downloads globally via ingestion queue (managed higher up)  # noqa: E501
                with self.session.get(
                    download_url, headers=headers, stream=True, timeout=(5.0, 60.0)
                ) as r:
                    r.raise_for_status()
                    # Use boto3 upload_fileobj which efficiently handles streaming without exhausting memory  # noqa: E501
                    self.s3_client.upload_fileobj(
                        r.raw, config.s3_bucket, s3_key, ExtraArgs={"ContentType": "image/tiff"}
                    )
                return f"s3://{config.s3_bucket}/{s3_key}"
            except Exception as e:
                asset_download_failure_total.inc()
                span.record_exception(e)
                logger.error(f"Failed to download asset {item_id}/{asset_key}: {e}")
                raise RuntimeError(f"Asset download failed: {e}")
