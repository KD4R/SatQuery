import logging
from typing import Optional
from packages.contracts import SceneRef
from packages.providers.bhoonidhi import BhoonidhiAdapter
from packages.providers.stac import STACProvider

logger = logging.getLogger(__name__)

class AssetResolver:
    """
    Implements P4-08: Asset resolver.
    Resolves abstract STAC item assets to physical download or S3 URLs.
    """
    def __init__(self):
        self.bhoonidhi = BhoonidhiAdapter()
        self.planetary_computer = STACProvider("planetary_computer", "https://planetarycomputer.microsoft.com/api/stac/v1")
        
    def resolve_asset_href(self, scene: SceneRef, asset_key: str) -> Optional[str]:
        if scene.provider == "bhoonidhi":
            return self.bhoonidhi.get_asset(scene.item_id, asset_key)
        elif scene.provider == "planetary_computer":
            return self.planetary_computer.get_asset(scene.item_id, asset_key)
        else:
            raise ValueError(f"Provider {scene.provider} not supported by resolver")
            
asset_resolver = AssetResolver()
