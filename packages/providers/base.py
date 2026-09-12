from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

class AbstractProvider(ABC):
    """
    Base interface for all EO Data Providers.
    """

    @abstractmethod
    def search(
        self,
        polygon: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        cloud_cover: float = 100.0,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search the provider catalog.
        Must respect implementation-specific rate limits and auth structures.
        """
        pass

    @abstractmethod
    def get_asset(self, item_id: str, asset_key: str) -> Optional[str]:
        """
        Resolve an item to a physical STAC asset href.
        """
        pass
