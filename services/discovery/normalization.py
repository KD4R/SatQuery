from typing import Dict, Any, List
from datetime import datetime
import uuid
import logging

from packages.contracts.data import Observation, SceneRef

logger = logging.getLogger(__name__)

def normalize_stac_item(provider_name: str, item: Dict[str, Any]) -> Observation:
    """
    Normalizes a provider-specific STAC item into the canonical Observation domain model.
    Handles extraction of required SceneRef attributes (platform, instrument, orbit, etc.).
    """
    properties = item.get("properties", {})
    
    # Extract acquisition time safely
    datetime_str = properties.get("datetime")
    if not datetime_str:
        raise ValueError(f"STAC item {item.get('id', 'unknown')} missing required 'datetime' property")
        
    try:
        acquired_at = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError(f"Invalid datetime format in item {item.get('id', 'unknown')}: {e}")

    platform = properties.get("platform", properties.get("eo:platform", "Unknown"))
    instruments = properties.get("instruments", [properties.get("eo:instrument", "Unknown")])
    instrument = instruments[0] if instruments else "Unknown"
    
    relative_orbit = properties.get("sat:relative_orbit")
    pass_direction = properties.get("sat:orbit_state")
    cloud_cover = properties.get("eo:cloud_cover")

    # Safely extract STAC href to avoid IndexError if links array is empty
    links = item.get("links", [])
    stac_href = ""
    for link in links:
        if link.get("rel") == "self":
            stac_href = link.get("href", "")
            break
    if not stac_href and links:
        stac_href = links[0].get("href", "")

    scene_ref = SceneRef(
        provider=provider_name,
        collection=item.get("collection", "Unknown"),
        item_id=item.get("id", "Unknown"),
        acquired_at=acquired_at,
        platform=platform,
        instrument=instrument,
        relative_orbit=relative_orbit,
        pass_direction=pass_direction,
        stac_href=stac_href,
        cloud_cover=cloud_cover
    )

    assets = {k: v.get("href", "") for k, v in item.get("assets", {}).items() if "href" in v}

    observation = Observation(
        observation_id=str(uuid.uuid4()),
        scene=scene_ref,
        geometry=item.get("geometry", {}),
        assets=assets,
        normalized_properties={
            "original_id": item.get("id"),
            "offline_status": item.get("_bhoonidhi_status")
        }
    )

    return observation

def normalize_pipeline(provider_name: str, items: List[Dict[str, Any]]) -> List[Observation]:
    """
    Pipeline to batch normalize STAC items ensuring individual failures do not break the whole batch.
    """
    observations = []
    for item in items:
        try:
            obs = normalize_stac_item(provider_name, item)
            observations.append(obs)
        except Exception as e:
            logger.error(f"Normalization failed for item {item.get('id', 'unknown')}: {e}")
            # Emit Prometheus metric here in real production environment to track normalization failures
            continue
    return observations
