from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

import pystac_client
from packages.providers.base import AbstractProvider

logger = logging.getLogger(__name__)


class STACProvider(AbstractProvider):
    """
    Generic STAC API provider for standard STAC catalogs (e.g., Planetary Computer).
    """

    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self._client = None

    @property
    def client(self) -> pystac_client.Client:
        if self._client is None:
            # We open the client with ignore_conformance for maximum compatibility
            # In a strict production system, we rely on the requests underlying retries.
            # pystac_client does not natively expose timeout in open(), so we handle timeouts on actual search.  # noqa: E501
            self._client = pystac_client.Client.open(self.url, ignore_conformance=True)  # type: ignore  # noqa: E501
        return self._client  # type: ignore

    def search(
        self,
        polygon: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        cloud_cover: float = 100.0,
        context: dict = None,  # type: ignore
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Standard STAC ItemSearch using GeoJSON polygon intersects and datetime range.
        """
        from services.eo_data.telemetry import tracer, inject_context_to_span

        context = context or {}
        with tracer.start_as_current_span(f"stac_search_{self.name}") as span:
            inject_context_to_span(span, context)
            try:
                datetime_str = f"{start_date.isoformat()}Z/{end_date.isoformat()}Z"

                search_args = {"intersects": polygon, "datetime": datetime_str, "query": {}}

                if cloud_cover < 100.0:
                    search_args["query"]["eo:cloud_cover"] = {"lt": cloud_cover}  # type: ignore

                if "collections" in kwargs:
                    search_args["collections"] = kwargs["collections"]

                search = self.client.search(**search_args)  # type: ignore

                items = list(search.items())
                logger.info(f"STACProvider '{self.name}' found {len(items)} items.")
                return [item.to_dict() for item in items]
            except Exception as e:
                span.record_exception(e)
                logger.error(f"STAC search failed on provider '{self.name}': {e}")
                raise

    def get_asset(self, item_id: str, asset_key: str, context: dict = None) -> Optional[str]:  # type: ignore  # noqa: E501
        from services.eo_data.telemetry import tracer, inject_context_to_span

        context = context or {}
        with tracer.start_as_current_span(f"stac_get_asset_{self.name}") as span:
            inject_context_to_span(span, context)
            try:
                item = self.client.get_item(item_id)
                if not item or asset_key not in item.assets:
                    return None
                return item.assets[asset_key].href
            except Exception as e:
                span.record_exception(e)
                logger.error(f"Failed to get asset '{asset_key}' for item '{item_id}': {e}")
                raise
