import logging
import rasterio
from rasterio.env import Env

logger = logging.getLogger(__name__)

def validate_raster(file_path: str) -> bool:
    """
    Implements P4-10: Raster validation.
    Checks raster integrity before processing to prevent malicious file exploits
    (e.g., decompression bombs or malformed GeoTIFFs).
    """
    try:
        # Use strict GDAL environment context to prevent exploitation during parsing
        # EMPTY_DIR prevents reading external sidecar files (path traversal risk)
        with Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_MAX_DATASET_POOL_SIZE=1):
            with rasterio.open(file_path) as src:
                if src.count < 1:
                    logger.error("Raster validation failed: No bands found.")
                    raise ValueError("Raster has no bands")
                
                # Enforce dimensions to prevent memory exhaustion
                if src.width > 30000 or src.height > 30000:
                    logger.error(f"Raster dimensions too large: {src.width}x{src.height}")
                    raise ValueError("Raster exceeds maximum allowed dimensions")
                    
                # Must be a recognized format
                if src.driver not in ["GTiff", "COG"]:
                    logger.warning(f"Unexpected raster driver: {src.driver}")
                    
                return True
    except rasterio.errors.RasterioIOError as e:
        from services.eo_data.telemetry import raster_validation_failure_total
        raster_validation_failure_total.inc()
        logger.error(f"Raster validation failed: Invalid or corrupted file. {e}")
        raise ValueError(f"Invalid or corrupted raster file: {file_path}")
