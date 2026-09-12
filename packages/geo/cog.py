import logging
import subprocess
import os

logger = logging.getLogger(__name__)


def generate_cog(source_path: str, target_path: str, context: dict = None) -> str:  # type: ignore
    """
    Implements P4-13: COG generation and overviews.
    Generates a Cloud Optimized GeoTIFF (COG) WITH overviews (pyramids) for fast zoom rendering.
    """
    logger.info(f"Generating COG with overviews for {source_path}")

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source raster not found: {source_path}")

    # 1. Build overviews on the source file first (or a temp copy if we don't want to mutate)
    # Using gdaladdo to build pyramid overviews (levels 2, 4, 8, 16, 32)
    addo_cmd = ["gdaladdo", "-r", "nearest", source_path, "2", "4", "8", "16", "32"]
    try:
        subprocess.run(addo_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"gdaladdo failed: {e.stderr}")
        raise RuntimeError(f"Failed to generate overviews: {e.stderr}")

    # 2. Translate to COG format, preserving overviews (COPY_SRC_OVERVIEWS=YES)
    cog_cmd = [
        "gdal_translate",
        source_path,
        target_path,
        "-of",
        "COG",
        "-co",
        "COMPRESS=DEFLATE",
        "-co",
        "COPY_SRC_OVERVIEWS=YES",
    ]
    try:
        subprocess.run(cog_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"gdal_translate failed: {e.stderr}")
        raise RuntimeError(f"Failed to generate COG: {e.stderr}")

    return target_path
