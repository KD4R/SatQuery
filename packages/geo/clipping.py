import logging
from typing import Dict, Any
import rasterio
from rasterio.mask import mask
from shapely.geometry import shape
from pyproj import Transformer

logger = logging.getLogger(__name__)

def clip_raster_to_aoi(source_path: str, target_path: str, aoi_geojson: Dict[str, Any]) -> str:
    """
    Implements P4-12: AOI clipping and windowed processing.
    Memory-efficient windowed clipping using rasterio mask.
    The AOI geojson is expected to be in EPSG:4326; it is reprojected to the
    raster CRS using pyproj + Shapely (no geopandas dependency required).
    """
    with rasterio.open(source_path) as src:
        logger.info(f"Clipping raster {source_path} to AOI")

        # Reproject AOI from EPSG:4326 to raster CRS using pyproj
        # src.crs can be a rasterio CRS object or a plain string (e.g. in tests)
        try:
            from pyproj import CRS as ProjCRS
            raster_crs = ProjCRS.from_user_input(src.crs)
            src_epsg = raster_crs.to_epsg()
        except Exception:
            src_epsg = 4326

        if src_epsg and src_epsg != 4326:
            transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{src_epsg}", always_xy=True)
            aoi_shape = shape(aoi_geojson)
            aoi_shape = _transform_geometry(aoi_shape, transformer)
        else:
            aoi_shape = shape(aoi_geojson)

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


def _transform_geometry(geom, transformer):
    """Apply a pyproj Transformer to a Shapely geometry."""
    from shapely.ops import transform
    return transform(transformer.transform, geom)
