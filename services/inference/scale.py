"""Declared backscatter scale per provider, dB conversion, and AOI rasterisation.

Why the scale is declared per provider
--------------------------------------
ADR-0007 D3: scale is declared data, never inferred from pixel values. The live
path reads Microsoft Planetary Computer ``sentinel-1-rtc`` assets, which are
radiometrically terrain-corrected gamma-nought in **linear power** (the
collection documents them as such; they are not in dB). The service used to
declare every raster as DECIBEL, so Otsu ran on linear values between ~0 and ~1
and the learned models were fed inputs an order of magnitude off their training
range. Local benchmark chips (Sen1Floods11) are distributed in dB, so a file
path with no provider keeps the DECIBEL declaration.

The table below is the one place that mapping lives. Adding a provider is a
reviewed change here, with a citation for its scale.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from packages.contracts import BackscatterScale, SceneRef
from ml.io.raster import Raster
from ml.sar.units import ensure_decibel

#: (provider, collection) -> scale of the pixel values as delivered.
#: Planetary Computer sentinel-1-rtc: gamma0 RTC, linear power.
DECLARED_SCALES: dict[tuple[str, str], BackscatterScale] = {
    ("planetary_computer", "sentinel-1-rtc"): BackscatterScale.POWER,
}


def _value(field) -> str:
    return str(getattr(field, "value", field) or "").lower()


def declared_scale_for(scene: SceneRef | None) -> BackscatterScale:
    """The declared scale of a scene's pixels. DECIBEL for local chips."""
    if scene is None:
        return BackscatterScale.DECIBEL
    return DECLARED_SCALES.get(
        (_value(scene.provider), _value(scene.collection)), BackscatterScale.DECIBEL
    )


def to_decibel(raster: Raster) -> Raster:
    """Return the raster expressed in dB (a no-op when it already is)."""
    if raster.spec.scale is BackscatterScale.DECIBEL:
        return raster
    data = np.stack(
        [ensure_decibel(raster.data[i], raster.spec.scale) for i in range(raster.data.shape[0])]
    ).astype(np.float32)
    data.setflags(write=False)
    return Raster(
        data=data,
        spec=raster.spec.model_copy(update={"scale": BackscatterScale.DECIBEL}),
        transform=raster.transform,
    )


def aoi_region(geometry: dict, raster: Raster) -> npt.NDArray[np.bool_]:
    """Rasterise a WGS84 Polygon/MultiPolygon onto the raster's grid.

    Returns True for pixels whose centre lies inside the polygon. Raises
    ``ValueError`` when the geometry is not a polygon or misses the raster.
    """
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom

    kind = (geometry or {}).get("type")
    if kind not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"expected a Polygon or MultiPolygon, got {kind!r}")
    projected = transform_geom("EPSG:4326", raster.spec.crs, geometry)
    inside = geometry_mask(
        [projected],
        out_shape=(raster.spec.height, raster.spec.width),
        transform=raster.transform,
        invert=True,
    )
    if not inside.any():
        raise ValueError("the AOI polygon does not overlap the scene")
    return inside
