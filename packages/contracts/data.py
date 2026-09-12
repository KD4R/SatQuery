from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class SceneRef(BaseModel):
    """
    Physical reference to an EO asset scene (as specified in Evidence contract FIG 4).
    """
    provider: str = Field(..., description="Provider name, e.g., 'bhoonidhi', 'planetary_computer'")
    collection: str = Field(..., description="STAC collection ID")
    item_id: str = Field(..., description="STAC item ID")
    acquired_at: datetime = Field(..., description="Acquisition timestamp")
    platform: str = Field(..., description="Satellite platform, e.g., 'EOS-04', 'Sentinel-1A'")
    instrument: str = Field(..., description="Sensor instrument name")
    relative_orbit: Optional[int] = Field(None, description="Relative orbit number (critical for SAR comparison)")
    pass_direction: Optional[str] = Field(None, description="'ASCENDING' or 'DESCENDING' (critical for SAR comparison)")
    stac_href: str = Field(..., description="Original STAC item href")
    cloud_cover: Optional[float] = Field(None, description="Tile-level cloud cover percentage")

class Observation(BaseModel):
    """
    Domain entity for a normalized observation containing STAC item references.
    """
    observation_id: str = Field(..., description="Internal canonical observation ID")
    scene: SceneRef = Field(..., description="Reference to the underlying STAC scene")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON footprint geometry")
    assets: Dict[str, str] = Field(..., description="Mapping of asset key (e.g., 'vh', 'visual') to its download/s3 href")
    normalized_properties: Dict[str, Any] = Field(default_factory=dict, description="Normalized EO metadata")
