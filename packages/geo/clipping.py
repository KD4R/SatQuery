import logging
from typing import Dict, Any
import rasterio
from rasterio.mask import mask
from shapely.geometry import shape

logger = logging.getLogger(__name__)

def clip_raster_to_aoi(source_path: str, target_path: str, aoi_geojson: Dict[str, Any]) -> str:
    """
    Implements P4-12: AOI clipping and windowed processing.
    Memory-efficient windowed clipping using rasterio mask.
    The AOI geojson is expected to be in the same CRS as the source raster.
    """
    aoi_shape = shape(aoi_geojson)
    
    with rasterio.open(source_path) as src:
        logger.info(f"Clipping raster {source_path} to AOI")
        
        # Windowed read/masking to prevent OOM on large scenes
        out_image, out_transform = mask(src, [aoi_shape], crop=True)
        out_meta = src.meta.copy()

        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

        with rasterio.open(target_path, "w", **out_meta) as dst:
            dst.write(out_image)
            
    return target_path
