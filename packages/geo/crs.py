import logging
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling

logger = logging.getLogger(__name__)

# Standardize on EPSG:32643 (UTM Zone 43N) for precise physical measurements in India.
# Using EPSG:4326 for area computation is explicitly banned by the PRD.
DEFAULT_PROJECTED_CRS = "EPSG:32643"

def normalize_crs(source_path: str, target_path: str, target_crs: str = DEFAULT_PROJECTED_CRS) -> str:
    """
    Implements P4-11: CRS normalization and reprojection.
    Ensures that the raster is in a projected coordinate system to allow accurate area measurement.
    """
    with rasterio.open(source_path) as src:
        src_crs = src.crs.to_string()
        if src_crs == target_crs:
            logger.info(f"Raster already in target CRS {target_crs}. Skipping reprojection.")
            # In production, we might symlink or copy here depending on the pipeline
            return source_path
            
        logger.info(f"Reprojecting from {src_crs} to {target_crs}")
        
        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )
        
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': target_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rasterio.open(target_path, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.nearest
                )
                
    return target_path
