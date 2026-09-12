from enum import Enum
from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field

class Provider(str, Enum):
    """Closed set, so an unknown provider is a validation error rather than an
    untracked data source appearing in provenance. Add new providers here."""
    BHOONIDHI = "bhoonidhi"
    PLANETARY_COMPUTER = "planetary_computer"
    ASF_HYP3 = "asf_hyp3"
    COPERNICUS_DATASPACE = "copernicus_dataspace"

class PassDirection(str, Enum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"

class SceneRef(BaseModel):
    """Physical reference to an EO asset scene (Evidence contract FIG 4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Provider = Field(..., description="Provider; add new ones to the enum")
    collection: str = Field(..., min_length=1, description="STAC collection ID")
    item_id: str = Field(..., min_length=1, description="STAC item ID")
    acquired_at: datetime = Field(..., description="Acquisition timestamp")
    platform: str = Field(..., min_length=1, description="e.g. EOS-04, Sentinel-1A")
    instrument: str = Field(..., min_length=1, description="Sensor instrument name")
    relative_orbit: Optional[int] = Field(..., description="Critical for SAR comparison")
    pass_direction: Optional[PassDirection] = Field(..., description="Critical for SAR comparison")
    stac_href: str = Field(..., min_length=1, description="Original STAC item href")
    cloud_cover: Optional[float] = Field(..., ge=0, le=100, description="Tile-level cloud %")

class AssetRef(BaseModel):
    """Reference to a physical asset."""
    href: str = Field(..., description="Download URL or S3 URI")
    media_type: Optional[str] = Field(None, description="MIME type of the asset")
    roles: Optional[list[str]] = Field(None, description="STAC roles for the asset")

class Observation(BaseModel):
    """
    Domain entity for a normalized observation containing STAC item references.
    """
    observation_id: str = Field(..., description="Internal canonical observation ID")
    scene: SceneRef = Field(..., description="Reference to the underlying STAC scene")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON footprint geometry")
    assets: Dict[str, AssetRef] = Field(..., description="Mapping of asset key to AssetRef")
    normalized_properties: Dict[str, Any] = Field(default_factory=dict, description="Normalized EO metadata")
