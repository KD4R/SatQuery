import logging
from typing import Dict, Any
from shapely.geometry import shape
import pyproj
from shapely.ops import transform
from packages.contracts import Observation

logger = logging.getLogger(__name__)

# Projection configuration. 
# PRD recommends EPSG:32643 (UTM 43N) for India/P4 area calculations.
# We explicitly project WGS84 GeoJSONs to UTM to ensure intersection areas are calculated
# in true physical meters, preventing severe inaccuracies at varying latitudes.
project_to_utm43n = pyproj.Transformer.from_crs("epsg:4326", "epsg:32643", always_xy=True).transform

def score_observation_quality(observation: Observation, aoi_polygon: Dict[str, Any]) -> float:
    """
    Implements P4-19: EO data quality scoring/enrichment.
    Calculates a quality score (0.0 to 1.0) based on cloud cover and AOI geometry overlap.
    A score of 1.0 means perfect overlap with 0% cloud cover.
    """
    try:
        aoi_shape = shape(aoi_polygon)
        obs_shape = shape(observation.geometry)
        
        # Project to UTM 43N to calculate accurate physical areas
        aoi_proj = transform(project_to_utm43n, aoi_shape)
        obs_proj = transform(project_to_utm43n, obs_shape)
        
        overlap_area = aoi_proj.intersection(obs_proj).area
        aoi_area = aoi_proj.area
    except Exception as e:
        logger.error(f"Geometry error during quality scoring: {e}")
        return 0.0
        
    if aoi_area == 0:
        coverage_score = 0.0
    else:
        coverage_score = min(overlap_area / aoi_area, 1.0)
        
    # 2. Cloud cover score (0.0 to 1.0)
    raw_cloud_cover = observation.scene.cloud_cover
    
    if raw_cloud_cover is None:
        # SAR often has None cloud_cover, which means clouds don't matter!
        if observation.scene.instrument and 'SAR' in observation.scene.instrument.upper():
            cloud_score = 1.0
        else:
            cloud_score = 0.5 
    else:
        cloud_score = max(0.0, 1.0 - (raw_cloud_cover / 100.0))
        
    # Composite score: Coverage is paramount. Clouds reduce quality of covered area.
    final_score = coverage_score * cloud_score
    
    # Enrich the observation properties with the computed score
    observation.normalized_properties["data_quality_score"] = round(final_score, 4)
    observation.normalized_properties["aoi_coverage_fraction"] = round(coverage_score, 4)
    
    logger.info(f"Observation {observation.observation_id} scored {final_score:.4f} (Coverage: {coverage_score:.2f}, Cloud: {cloud_score:.2f})")
    return final_score
