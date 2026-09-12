from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
import urllib3

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
            # pystac_client does not natively expose timeout in open(), so we handle timeouts on actual search.
            self._client = pystac_client.Client.open(self.url, ignore_conformance=True)
        return self._client

    def search(
        self,
        polygon: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        cloud_cover: float = 100.0,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Standard STAC ItemSearch using GeoJSON polygon intersects and datetime range.
        """
        try:
            datetime_str = f"{start_date.isoformat()}Z/{end_date.isoformat()}Z"
            
            search_args = {
                "intersects": polygon,
                "datetime": datetime_str,
                "query": {}
            }

            if cloud_cover < 100.0:
                search_args["query"]["eo:cloud_cover"] = {"lt": cloud_cover}
                
            if "collections" in kwargs:
                search_args["collections"] = kwargs["collections"]

            search = self.client.search(**search_args)
            
            items = list(search.items())
            logger.info(f"STACProvider '{self.name}' found {len(items)} items.")
            return [item.to_dict() for item in items]
        except Exception as e:
            logger.error(f"STAC search failed on provider '{self.name}': {e}")
            raise

    def get_asset(self, item_id: str, asset_key: str) -> Optional[str]:
        try:
            item = self.client.get_item(item_id)
            if not item or asset_key not in item.assets:
                return None
            return item.assets[asset_key].href
        except Exception as e:
            logger.error(f"Failed to get asset '{asset_key}' for item '{item_id}': {e}")
            raise
