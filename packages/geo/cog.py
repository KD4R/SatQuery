import logging
import os
import subprocess

logger = logging.getLogger(__name__)

def generate_cog(source_path: str, target_path: str) -> str:
    """
    Implements P4-13: COG generation and overviews.
    Uses GDAL via subprocess to convert standard GeoTIFFs to Cloud Optimized GeoTIFFs (COG).
    This ensures rapid dynamic tile serving by TiTiler.
    """
    logger.info(f"Generating COG from {source_path} to {target_path}")
    
    # We use gdal_translate for COG creation, explicitly adding overviews
    command = [
        "gdal_translate",
        source_path,
        target_path,
        "-of", "COG",
        "-co", "COMPRESS=DEFLATE",
        "-co", "OVERVIEWS=IGNORE_EXISTING" # Force standard overview generation
    ]
    
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"GDAL COG generation failed: {e.stderr}")
        raise RuntimeError(f"Failed to generate COG: {e.stderr}")
        
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"COG generation silently failed, target {target_path} not found.")
        
    return target_path
