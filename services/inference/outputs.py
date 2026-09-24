"""Serialise an analysis's water mask as the two artefacts the contract names.

``Analysis.raster_refs``  -- the mask itself, a single-band GeoTIFF on the grid the
                             area was measured on (P3 work pack, task 2).
``Analysis.geometry_ref`` -- the same mask vectorised to GeoJSON, for the map.

Before this, the service computed the mask, measured it, and threw it away: both
fields were hardcoded empty. A hectare figure the caller cannot see the shape of
is a number they have to take on trust, which is the thing the whole evidence
chain exists to avoid.

The one invariant that matters
------------------------------
Both artefacts are built from the *postprocessed* mask -- speckle removed,
permanent water subtracted, minimum mapping unit applied -- which is exactly the
array ``area_hectares`` measured. Serialise the raw model output instead and the
polygons on the map would disagree with the area in the report, by the permanent
water and the specks, with nothing on screen to say why. Checked in
test_outputs.py by re-measuring the GeoJSON and comparing it to the reported area.

GeoJSON is reprojected to EPSG:4326, because RFC 7946 requires WGS84 and a
browser map assumes it. The GeoTIFF stays in the analysis CRS, because it is the
measured artefact and resampling a class mask would change it.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import numpy.typing as npt
import rasterio
from rasterio import features
from rasterio.io import MemoryFile
from rasterio.warp import transform_geom

#: Vertex tolerance for the GeoJSON, in the analysis CRS's units (metres, since
#: the raster is reprojected to UTM before anything measures it). One pixel is
#: ~10 m; simplifying at half a pixel removes the staircase without moving an
#: edge by more than the sensor can resolve. The GeoTIFF is never simplified.
SIMPLIFY_TOLERANCE_M = 5.0

#: A polygon smaller than this is dropped from the GeoJSON only. It cannot be
#: smaller than the minimum mapping unit already applied, so this only catches
#: slivers created by simplification.
_MIN_RING_POINTS = 4


def mask_geotiff(mask: npt.NDArray[np.bool_], *, transform: Any, crs: Any) -> bytes:
    """The mask as a compressed uint8 GeoTIFF: 1 water, 0 not water, 255 nodata."""
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2-D, got shape {mask.shape}")
    height, width = mask.shape
    data = mask.astype(np.uint8)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "uint8",
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
        "nodata": 255,
        "tiled": width >= 256 and height >= 256,
    }
    with MemoryFile() as memfile:
        with memfile.open(**profile) as dataset:
            dataset.write(data, 1)
            dataset.update_tags(1, meaning="1=water 0=not-water", product="satquery-water-mask")
        return bytes(memfile.read())


def mask_geojson(
    mask: npt.NDArray[np.bool_],
    *,
    transform: Any,
    crs: Any,
    pixel_area_m2: float,
    properties: dict[str, Any] | None = None,
) -> bytes:
    """The mask as an RFC 7946 FeatureCollection in EPSG:4326.

    Each feature carries ``area_ha`` measured *before* reprojection, from its pixel
    count, so the per-feature areas sum to the reported area exactly rather than
    approximately. Measuring the reprojected polygon would reintroduce the
    geographic-CRS area error ml.geo.area exists to prevent.
    """
    from shapely.geometry import mapping, shape

    if not mask.any():
        collection: dict[str, Any] = {
            "type": "FeatureCollection",
            "features": [],
            "properties": dict(properties or {}),
        }
        return json.dumps(collection, separators=(",", ":")).encode()

    labels, count = _label(mask)
    area_by_label = np.bincount(labels.ravel(), minlength=count + 1) * pixel_area_m2

    features_out: list[dict[str, Any]] = []
    # connectivity=8 to match _label(). rasterio defaults to 4, which would split a
    # diagonally joined component into several polygons -- each then stamped with
    # the whole component's area, double-counting it in the per-feature sums.
    for geometry, value in features.shapes(
        labels.astype(np.int32), mask=mask, transform=transform, connectivity=8
    ):
        label = int(value)
        if label == 0:
            continue
        polygon = shape(geometry).simplify(SIMPLIFY_TOLERANCE_M, preserve_topology=True)
        if polygon.is_empty:
            continue
        wgs84 = transform_geom(crs, "EPSG:4326", mapping(polygon))
        exterior = wgs84["coordinates"][0] if wgs84["type"] == "Polygon" else None
        if exterior is not None and len(exterior) < _MIN_RING_POINTS:
            continue
        features_out.append(
            {
                "type": "Feature",
                "id": f"water-{label:05d}",
                "geometry": wgs84,
                "properties": {
                    "class": "water",
                    "area_ha": round(float(area_by_label[label]) / 10_000.0, 4),
                },
            }
        )

    features_out.sort(key=lambda f: -f["properties"]["area_ha"])
    collection = {
        "type": "FeatureCollection",
        "features": features_out,
        "properties": dict(properties or {}),
    }
    return json.dumps(collection, separators=(",", ":")).encode()


def _label(mask: npt.NDArray[np.bool_]) -> tuple[npt.NDArray[np.int32], int]:
    """8-connected components, so each polygon gets a stable label and area."""
    from scipy import ndimage

    structure = np.ones((3, 3), dtype=bool)
    labels, count = ndimage.label(mask, structure=structure)
    return labels.astype(np.int32), int(count)


__all__ = ["mask_geojson", "mask_geotiff", "SIMPLIFY_TOLERANCE_M", "rasterio"]
