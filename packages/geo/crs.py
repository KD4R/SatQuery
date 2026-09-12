import logging
import math
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling, transform_bounds

logger = logging.getLogger(__name__)


def utm_epsg_for(lon: float, lat: float) -> str:
    """Calculate the correct UTM EPSG code for a given longitude and latitude."""
    if lat > 84 or lat < -80:
        raise ValueError("UTM is undefined beyond polar bounds (+84/-80).")
    zone = math.floor((lon + 180) / 6) + 1
    if lat >= 0:
        return f"EPSG:{32600 + zone}"
    else:
        return f"EPSG:{32700 + zone}"


def is_projected(crs: rasterio.crs.CRS) -> bool:
    return crs.is_projected  # type: ignore


def assert_projected(crs: rasterio.crs.CRS) -> None:
    if not is_projected(crs):
        raise ValueError("CRS must be projected, not geographic.")


def normalize_crs(source_path: str, target_path: str, target_crs: str = None) -> str:  # type: ignore  # noqa: E501
    """
    Implements P4-11: CRS normalization and reprojection.
    Dynamically computes the correct UTM zone if `target_crs` is not provided.
    """
    with rasterio.open(source_path) as src:
        if target_crs is None:
            left, bottom, right, top = src.bounds
            bounds_4326 = transform_bounds(src.crs, "EPSG:4326", left, bottom, right, top)
            lon = (bounds_4326[0] + bounds_4326[2]) / 2
            lat = (bounds_4326[1] + bounds_4326[3]) / 2
            target_crs = utm_epsg_for(lon, lat)

        src_crs = src.crs.to_string()
        if src_crs == target_crs:
            logger.info(f"Raster already in target CRS {target_crs}. Skipping reprojection.")
            return source_path

        logger.info(f"Reprojecting from {src_crs} to {target_crs}")

        transform, width, height = calculate_default_transform(
            src.crs, target_crs, src.width, src.height, *src.bounds
        )

        kwargs = src.meta.copy()
        kwargs.update({"crs": target_crs, "transform": transform, "width": width, "height": height})

        with rasterio.open(target_path, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=target_crs,
                    resampling=Resampling.nearest,
                )

    return target_path
