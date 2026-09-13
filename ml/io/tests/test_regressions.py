"""Regression tests for defects found in review of the foundation commit.

Their shared property is what makes them worth keeping: **each one passed
silently before the fix.** Not one produced an exception, a warning or a visibly
odd value -- they produced plausible wrong numbers, which is the failure mode this
subsystem exists to prevent, and they got past a reviewer who had just written the
trap list.

Distributed from a single module into each package's own tests at review
(PR #17), to follow the repository's co-location convention.

Reference: https://github.com/KD4R/SatQuery/pull/17
"""

from __future__ import annotations


import numpy as np
import pytest

from packages.contracts import BackscatterScale, Polarization, RasterSpec
from ml.io.preflight import validate_finite_fraction
from services.inference.validation import ALLOWED_SCHEMES

pytestmark = pytest.mark.unit


def test_finite_nodata_sentinel_is_counted_as_invalid() -> None:
    """A raster that is 90% ``-9999`` reported 100% valid and passed the gate.

    GeoTIFF has no NaN convention for integer bands, so finite sentinels are
    ordinary, not exotic. Checking ``isfinite`` alone fails open on precisely the
    input this function exists to reject.
    """
    array = np.full((10, 10), -9999.0)
    array[:1, :] = -12.0  # 10% real observations

    assert validate_finite_fraction(array, minimum=0.5) == pytest.approx(1.0)

    with pytest.raises(ValueError, match="valid"):
        validate_finite_fraction(array, minimum=0.5, nodata=-9999.0)


def test_s3_is_no_longer_advertised() -> None:
    """It never worked: in ``s3://bucket/key`` the bucket sits in the host
    position, so the host check compared a bucket name against HTTPS hostnames and
    rejected every such URL. A capability that always fails is worse than an
    absent one, because a caller builds against it.
    """
    assert "s3" not in ALLOWED_SCHEMES
    assert ALLOWED_SCHEMES == frozenset({"https"})


def test_nan_nodata_still_works_when_a_sentinel_is_also_declared() -> None:
    array = np.full((10, 10), np.nan)
    array[:8, :] = -12.0
    assert validate_finite_fraction(array, minimum=0.5, nodata=-9999.0) == pytest.approx(0.8)


def test_bounds_are_unchanged_for_north_up_and_correct_under_rotation() -> None:
    """``Raster.bounds`` took two opposite corners, which is only right north-up.

    Two claims, pinned together because the second is the reason for the change
    and the first is the reason it is safe to make on a branch carrying committed
    accuracy figures.

    North-up: the four-corner hull and the two-corner box agree exactly, so no
    number in reports/evaluation.md moves.

    Rotated: they do not agree, and the two-corner box is the smaller one -- it
    omits the corners that stick out. Nothing raises; the extent is simply wrong,
    which is how an AOI ends up quietly clipped.
    """
    from affine import Affine

    from ml.io.raster import Raster

    height, width = 512, 512

    def two_corner(transform: Affine) -> tuple[float, float, float, float]:
        west, north = transform * (0, 0)
        east, south = transform * (width, height)
        return (min(west, east), min(north, south), max(west, east), max(north, south))

    spec = RasterSpec(
        band_order=(Polarization.VV, Polarization.VH),
        scale=BackscatterScale.DECIBEL,
        dtype="float32",
        crs="EPSG:32643",
        width=width,
        height=height,
        pixel_size_m=(10.0, 10.0),
        nodata=None,
    )

    def raster_with(transform: Affine) -> Raster:
        return Raster(
            data=np.zeros((2, height, width), dtype=np.float32),
            spec=spec,
            transform=transform,
        )

    north_up = Affine.translation(500000.0, 4000000.0) * Affine.scale(10.0, -10.0)
    assert raster_with(north_up).bounds == pytest.approx(two_corner(north_up))

    rotated = north_up * Affine.rotation(30.0)
    hull = raster_with(rotated).bounds
    box = two_corner(rotated)
    assert hull != pytest.approx(box)

    hull_width = hull[2] - hull[0]
    box_width = box[2] - box[0]
    assert hull_width > box_width, "the two-corner form under-reports the extent"
