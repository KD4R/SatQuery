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

from decimal import Decimal

import numpy as np
import pytest
from pydantic import ValidationError

from packages.contracts.crs_policy import is_area_safe, is_projected
from ml.geo.area import area_hectares, pixel_area_m2
from ml.geo.crs import CRSError, assert_area_safe
from packages.contracts import Measurement, MeasurementUnit

pytestmark = pytest.mark.unit


def test_web_mercator_is_projected_but_not_area_safe() -> None:
    """The distinction the original guard collapsed.

    EPSG:3857 measures in metres, so it is legitimately projected. Its scale
    factor is 1/cos(latitude) in both axes, so multiplying its pixel dimensions
    overstates area by 1/cos^2(latitude): about 3% at Kerala, 15% at 30 N. Nothing
    raises, and the error grows with distance from the equator -- so it is largest
    exactly where a reviewer is least likely to have a mental baseline.
    """
    assert is_projected("EPSG:3857") is True
    assert is_area_safe("EPSG:3857") is False


def test_area_in_web_mercator_is_refused_with_the_reason() -> None:
    with pytest.raises(CRSError, match="conformal"):
        assert_area_safe("EPSG:3857", operation="compute pixel area")


def test_pixel_area_refuses_web_mercator() -> None:
    with pytest.raises(CRSError):
        pixel_area_m2((10.0, 10.0), "EPSG:3857")


def test_utm_remains_area_safe() -> None:
    """The guard has to keep admitting what the pipeline actually uses."""
    for crs in ("EPSG:32643", "EPSG:32644", "EPSG:32646", "EPSG:32733"):
        assert is_area_safe(crs) is True
        assert_area_safe(crs, operation="compute pixel area")


@pytest.mark.parametrize(
    "crs",
    [
        "EPSG:4258",  # ETRS89 -- geographic, absent from the original blacklist
        "EPSG:4283",  # GDA94  -- likewise
        "EPSG:3857",  # projected but not area-safe
        "not-a-crs",  # not an identifier at all
        "PROJCS[...]",  # WKT, unparseable without pyproj
        "EPSG:",  # malformed
    ],
)
def test_physical_measurement_refuses_every_unsafe_crs(crs: str, scene_pre) -> None:
    """A blacklist of five identifiers fails open; this is the point of the change.

    Each of these constructed a valid ``Measurement`` before the fix. The last
    three are the sharpest: an unparseable CRS is not a known-good one, and
    treating "not on my list of bad values" as "good" is how a typo becomes a
    hectare figure.
    """
    with pytest.raises(ValidationError):
        Measurement(
            name="inundated_area",
            value=Decimal("12.5"),
            unit=MeasurementUnit.HECTARES,
            produced_by="test",
            code_version="0.0.0",
            crs=crs,
            derived_from=(scene_pre,),
        )


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_pixel_area_refuses_non_finite_dimensions(bad: float) -> None:
    """``inf > 0`` is True, so the positivity check alone let infinity through.

    ``pixel_area_m2((inf, 10))`` returned ``inf``, which ``area_hectares`` then
    formatted into a Decimal and attached to a Measurement as a real number.
    """
    with pytest.raises(ValueError, match="finite"):
        pixel_area_m2((bad, 10.0), "EPSG:32643")
    with pytest.raises(ValueError, match="finite"):
        pixel_area_m2((10.0, bad), "EPSG:32643")


@pytest.mark.parametrize("stray", [-1, 2, 255])
def test_area_refuses_a_mask_that_is_not_zero_or_one(stray: int, scene_pre) -> None:
    """``count_nonzero`` counted every non-zero value as inundated.

    Handing ``area_hectares`` a raw Sen1Floods11 label array adds its entire -1
    no-data border to the flood; handing it a multiclass prediction adds every
    cloud pixel. Both are plausible mistakes, neither raised, and the error
    inflates the headline figure -- biasing in the alarming direction. The same
    guard was already on ``confusion()`` and had not been mirrored here.
    """
    mask = np.zeros((4, 4), dtype=np.int16)
    mask[0, 0] = 1
    mask[1, 1] = stray

    with pytest.raises(ValueError, match="neither 0 nor 1"):
        area_hectares(
            mask,
            pixel_size_m=(10.0, 10.0),
            crs="EPSG:32643",
            derived_from=(scene_pre,),
            code_version="0.0.0",
        )


def test_area_accepts_boolean_and_zero_one_masks(scene_pre) -> None:
    """The guard must not refuse the two encodings the pipeline actually produces."""
    boolean = np.zeros((10, 10), dtype=bool)
    boolean[:5, :] = True
    integral = boolean.astype(np.int16)

    def measure(mask: np.ndarray) -> Decimal:
        return area_hectares(
            mask,
            pixel_size_m=(10.0, 10.0),
            crs="EPSG:32643",
            derived_from=(scene_pre,),
            code_version="0.0.0",
        ).value

    assert measure(boolean) == measure(integral)
