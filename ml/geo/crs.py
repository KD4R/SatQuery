"""Coordinate reference system helpers and the projected-CRS guard.

Scope note
----------
This module deliberately does **not** depend on ``pyproj`` or ``rasterio``. The
first commit keeps runtime dependencies to NumPy and pydantic so the whole test
suite runs offline with no geospatial stack installed, which is what lets CI stay
fast and lets the contracts be validated anywhere.

The consequence is that :func:`assert_projected` uses an allowlist rather than a
general CRS database lookup. That is a conservative choice: an unrecognised CRS is
rejected rather than assumed to be projected. When ``pyproj`` enters the project
(needed for actual reprojection, which is not in this commit), this function should
be widened to ask ``pyproj.CRS(...).is_projected`` and the allowlist kept only as a
fast path.
"""

from __future__ import annotations

import math

from ml.contracts.measurement import GEOGRAPHIC_CRS


class CRSError(ValueError):
    """Raised when a CRS is unsuitable for the operation requested."""


def utm_epsg_for(lon: float, lat: float) -> str:
    """Return the EPSG identifier of the UTM zone containing ``(lon, lat)``.

    UTM zones are 6 degrees of longitude wide and numbered 1..60 eastward from the
    antimeridian. Northern-hemisphere zones are EPSG:326xx, southern are EPSG:327xx.

    This is arithmetic rather than a lookup, so it does not handle the handful of
    irregular zones (Norway's zone 32V, and the Svalbard zones 31X-37X). Those
    exceptions do not affect the Indian AOIs this project targets, but the
    limitation is recorded here rather than discovered later.

    Parameters
    ----------
    lon, lat
        Coordinates in degrees, typically the centroid of the AOI.

    Returns
    -------
    str
        e.g. ``"EPSG:32643"`` for most of peninsular India.

    Raises
    ------
    CRSError
        If the coordinates are outside valid geographic ranges. UTM is also
        undefined beyond about 84 N / 80 S; that is checked too, because silently
        returning a zone for a polar coordinate would produce a badly distorted
        area rather than an error.
    """
    if not math.isfinite(lon) or not math.isfinite(lat):
        raise CRSError(f"non-finite coordinates: lon={lon!r} lat={lat!r}")
    if not (-180.0 <= lon <= 180.0):
        raise CRSError(f"longitude {lon} outside [-180, 180]")
    if not (-90.0 <= lat <= 90.0):
        raise CRSError(f"latitude {lat} outside [-90, 90]")
    if not (-80.0 <= lat <= 84.0):
        raise CRSError(
            f"latitude {lat} is outside the UTM domain (-80 to 84); "
            "use a polar stereographic projection instead"
        )

    # floor((lon + 180) / 6) + 1 gives 1..60. The special case is lon == 180
    # exactly, which would otherwise yield 61.
    # math.floor already returns an int in Python 3; no cast needed.
    zone = math.floor((lon + 180.0) / 6.0) + 1
    zone = min(zone, 60)

    base = 32600 if lat >= 0 else 32700
    return f"EPSG:{base + zone}"


def is_projected(crs: str) -> bool:
    """Best-effort check that ``crs`` measures in linear units rather than degrees.

    Conservative: returns ``True`` only for CRS identifiers we positively recognise
    as projected. Anything unrecognised returns ``False`` so that callers refuse
    rather than guess.
    """
    normalised = crs.strip().upper()
    if normalised in GEOGRAPHIC_CRS:
        return False
    if not normalised.startswith("EPSG:"):
        # Could be a WKT string or a PROJ pipeline. We cannot parse those without
        # pyproj, so we decline to vouch for it.
        return False
    try:
        code = int(normalised.split(":", 1)[1])
    except (IndexError, ValueError):
        return False
    # UTM north (32601-32660) and UTM south (32701-32760).
    if 32601 <= code <= 32660 or 32701 <= code <= 32760:
        return True
    # Web Mercator. Recognised as projected, but note it is *not* equal-area, so it
    # is a poor choice for measuring extent -- that judgement belongs to the caller,
    # which knows whether it is measuring or merely displaying.
    return code == 3857


def assert_projected(crs: str, *, operation: str) -> None:
    """Raise unless ``crs`` is safe to take a physical measurement in.

    This is the guard that stops the single most common geospatial defect: an area
    computed in EPSG:4326 and reported in hectares. The resulting number is wrong
    by a latitude-dependent factor, and because it is internally consistent it
    survives casual review.

    Parameters
    ----------
    crs
        CRS identifier to check.
    operation
        What the caller was about to do, used in the error message so the failure
        points at the offending call site.
    """
    if not is_projected(crs):
        raise CRSError(
            f"cannot {operation} in {crs}: a projected CRS is required. "
            "Degrees are not metres and the conversion factor varies with latitude. "
            "Reproject to the local UTM zone first (see utm_epsg_for)."
        )
