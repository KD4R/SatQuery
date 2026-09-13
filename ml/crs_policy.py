"""Which coordinate reference systems may be used for which purpose.

Why this is its own module
--------------------------
Three separate call sites need the same answer to "is this CRS safe to measure
in?" -- ``Measurement`` at contract construction, ``pixel_area_m2`` before it
multiplies, and ``assert_area_safe`` for anyone else. Before this module the
policy existed in two places that disagreed: ``Measurement`` carried a *blacklist*
of five geographic identifiers, while ``ml.geo.crs`` carried a positive allowlist.
A blacklist is the wrong shape for a safety guard -- it fails open. ``EPSG:4258``
(ETRS89, degrees) and the string ``"not-a-crs"`` both passed the contract check.

Keeping the policy here also removes an odd dependency edge: ``ml.geo`` previously
imported from ``ml.contracts`` to reach ``GEOGRAPHIC_CRS``. This module depends on
nothing, so both layers can import it without either depending on the other.

Two questions, deliberately distinct
------------------------------------
``is_projected`` asks whether a CRS measures in linear units at all. That is the
question you ask before doing geometry.

``is_area_safe`` asks whether a CRS's linear units are close enough to true ground
distance that multiplying two of them yields a defensible area. That is a strictly
stronger question, and the distinction is not pedantic:

    EPSG:3857 (Web Mercator) is projected. It is also conformal, with a scale
    factor of 1/cos(latitude) in both axes, so an area computed from its pixel
    dimensions is inflated by 1/cos^2(latitude) -- about 3% at Kerala, 15% at
    30 N, 100% at 60 N. Nothing raises. The number just grows with distance from
    the equator.

Treating "projected" as sufficient for area is how a display projection ends up
in a measurement. The two predicates exist so that mistake has to be made
deliberately.
"""

from __future__ import annotations

#: CRS identifiers that are geographic (degrees), not projected (metres).
#: Retained as a named set because the error messages cite it, but note that it is
#: *not* what the guards test against -- see the module docstring on blacklists.
GEOGRAPHIC_CRS = frozenset(
    {
        "EPSG:4326",  # WGS 84 lat/lon -- the usual offender
        "EPSG:4979",  # WGS 84 3D
        "EPSG:4269",  # NAD83
        "EPSG:4258",  # ETRS89
        "OGC:CRS84",  # WGS 84 lon/lat axis order
        "CRS84",
    }
)

#: Projected CRSs that are *not* safe for area, mapped to the reason. Recognised
#: explicitly so the error can say why rather than "unrecognised CRS", which would
#: send the caller looking for a typo.
_PROJECTED_BUT_NOT_AREA_SAFE = {
    3857: (
        "Web Mercator is conformal, not equal-area: its scale factor is "
        "1/cos(latitude) in both axes, so an area derived from its pixel size is "
        "inflated by 1/cos^2(latitude) -- roughly 3% at 10 N and 15% at 30 N"
    ),
    900913: "a legacy alias of Web Mercator (EPSG:3857); same conformal distortion",
}


def _epsg_code(crs: str) -> int | None:
    """Return the numeric EPSG code, or ``None`` if ``crs`` is not an EPSG string.

    WKT strings and PROJ pipelines return ``None``: they cannot be parsed without
    pyproj, and this module declines to vouch for what it cannot read.
    """
    normalised = crs.strip().upper()
    if not normalised.startswith("EPSG:"):
        return None
    try:
        return int(normalised.split(":", 1)[1])
    except (IndexError, ValueError):
        return None


def _is_utm(code: int) -> bool:
    """WGS 84 / UTM zone 1N-60N (32601-32660) or 1S-60S (32701-32760)."""
    return 32601 <= code <= 32660 or 32701 <= code <= 32760


def is_projected(crs: str) -> bool:
    """Whether ``crs`` measures in linear units rather than degrees.

    Conservative by construction: returns ``True`` only for identifiers positively
    recognised as projected, so an unrecognised CRS causes the caller to refuse
    rather than to guess.
    """
    code = _epsg_code(crs)
    if code is None:
        return False
    return _is_utm(code) or code in _PROJECTED_BUT_NOT_AREA_SAFE


def is_area_safe(crs: str) -> bool:
    """Whether an area may be computed by multiplying ``crs``'s linear units.

    Stronger than :func:`is_projected`. Currently satisfied only by the WGS 84 UTM
    zones, whose scale error is at most about 0.04% within the zone -- four orders
    of magnitude below the uncertainty of a 10 m SAR water mask, and therefore not
    worth modelling.

    Adding a projection here is a deliberate, reviewed act. Equal-area families
    (Albers, Lambert azimuthal, the Indian national grids) belong here once one is
    actually used and its parameters are pinned; adding them speculatively would
    mean shipping an allowlist entry nobody has checked.
    """
    code = _epsg_code(crs)
    if code is None:
        return False
    return _is_utm(code)


def explain_unsafe_for_area(crs: str) -> str:
    """A specific reason ``crs`` was refused for area, for the error message."""
    normalised = crs.strip().upper()
    code = _epsg_code(crs)

    if normalised in GEOGRAPHIC_CRS or (code is not None and 4000 <= code <= 4999):
        return (
            "it is geographic (degrees). One degree of longitude is about 111 km at "
            "the equator and 78 km at 45 degrees, so the error moves with latitude"
        )
    if code is not None and code in _PROJECTED_BUT_NOT_AREA_SAFE:
        return _PROJECTED_BUT_NOT_AREA_SAFE[code]
    if code is None:
        return (
            "it is not an EPSG identifier this build can verify. WKT strings and "
            "PROJ pipelines need pyproj, which is not a dependency here, so they "
            "are refused rather than assumed safe"
        )
    return (
        "it is not on the area-safe allowlist. Only WGS 84 UTM zones are accepted; "
        "reproject to the local zone first (see ml.geo.crs.utm_epsg_for)"
    )
