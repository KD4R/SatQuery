"""CRS handling and area measurement.

The assertions here are hand-computable on purpose. A 10 m pixel is 100 m2, so
100 water pixels is exactly 1 hectare -- no tolerance needed, and any refactor that
changes the answer changes it visibly.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from packages.contracts import MeasurementUnit, SceneRef
from ml.geo.area import PRODUCER, area_hectares, pixel_area_m2
from ml.geo.crs import CRSError, assert_projected, is_projected, utm_epsg_for

# CI selects tests by marker (`pytest -m unit`); an unmarked test never runs.
# Everything in this module is a fast, offline, no-I/O unit test.
pytestmark = pytest.mark.unit

# --------------------------------------------------------------------------- #
# UTM zone arithmetic                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("lon", "lat", "expected"),
    [
        # Kuttanad, Kerala -- the flagship flood AOI. Zone 43N.
        (76.4, 9.4, "EPSG:32643"),
        # Guntur, Andhra Pradesh -- the demo scenario in the master PRD. Zone 44N.
        (80.44, 16.31, "EPSG:32644"),
        # Southern hemisphere picks the 327xx band.
        (76.4, -9.4, "EPSG:32743"),
        # Zone boundaries: -180 is the western edge of zone 1.
        (-180.0, 0.0, "EPSG:32601"),
        # +180 clamps to zone 60 rather than overflowing to 61.
        (180.0, 0.0, "EPSG:32660"),
    ],
)
def test_utm_epsg_for_known_locations(lon: float, lat: float, expected: str) -> None:
    assert utm_epsg_for(lon, lat) == expected


def test_utm_epsg_rejects_polar_latitudes() -> None:
    """UTM is undefined beyond ~84N/80S; returning a zone there would distort area."""
    with pytest.raises(CRSError, match="UTM domain"):
        utm_epsg_for(0.0, 87.0)


def test_utm_epsg_rejects_non_finite() -> None:
    with pytest.raises(CRSError, match="non-finite"):
        utm_epsg_for(float("nan"), 10.0)


# --------------------------------------------------------------------------- #
# The projected-CRS guard                                                      #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("crs", ["EPSG:32643", "EPSG:32760", "EPSG:3857"])
def test_is_projected_accepts_projected(crs: str) -> None:
    assert is_projected(crs) is True


@pytest.mark.parametrize(
    "crs",
    [
        "EPSG:4326",  # the usual offender
        "OGC:CRS84",
        "EPSG:4269",
        "not-a-crs",  # unrecognised -> conservative False
        "EPSG:99999",  # unknown code -> conservative False
    ],
)
def test_is_projected_rejects_geographic_and_unknown(crs: str) -> None:
    """Conservative by design: anything we cannot vouch for is refused."""
    assert is_projected(crs) is False


def test_assert_projected_names_the_operation() -> None:
    with pytest.raises(CRSError, match="measure area"):
        assert_projected("EPSG:4326", operation="measure area")


# --------------------------------------------------------------------------- #
# Pixel area                                                                   #
# --------------------------------------------------------------------------- #


def test_pixel_area_is_exact_for_ten_metre_pixels() -> None:
    assert pixel_area_m2((10.0, 10.0), "EPSG:32643") == 100.0


def test_pixel_area_refuses_geographic_crs() -> None:
    """This is the guard that stops hectares being computed from degrees."""
    with pytest.raises(CRSError):
        pixel_area_m2((0.0001, 0.0001), "EPSG:4326")


def test_pixel_area_refuses_nonpositive_size() -> None:
    with pytest.raises(ValueError, match="positive magnitudes"):
        pixel_area_m2((10.0, 0.0), "EPSG:32643")


# --------------------------------------------------------------------------- #
# area_hectares -- the only user-visible number                                #
# --------------------------------------------------------------------------- #


def test_area_hectares_is_exact_and_hand_checkable(scene_pre: SceneRef) -> None:
    """100 pixels x 100 m2 = 10,000 m2 = exactly 1.0 hectare."""
    mask = np.zeros((50, 50), dtype=bool)
    mask[:10, :10] = True  # 100 pixels

    measurement = area_hectares(
        mask,
        pixel_size_m=(10.0, 10.0),
        crs="EPSG:32643",
        derived_from=[scene_pre],
        code_version="0.1.0",
    )

    assert measurement.value == Decimal("1.0")
    assert measurement.unit is MeasurementUnit.HECTARES


def test_area_hectares_attaches_full_provenance(scene_pre: SceneRef) -> None:
    """The contract's whole purpose: the number arrives with its audit trail."""
    mask = np.ones((10, 10), dtype=bool)

    measurement = area_hectares(
        mask,
        pixel_size_m=(10.0, 10.0),
        crs="EPSG:32643",
        derived_from=[scene_pre],
        code_version="0.1.0",
    )

    assert measurement.produced_by == PRODUCER
    assert measurement.code_version == "0.1.0"
    assert measurement.crs == "EPSG:32643"
    assert measurement.derived_from == (scene_pre,)


def test_area_hectares_refuses_geographic_crs(scene_pre: SceneRef) -> None:
    with pytest.raises(CRSError):
        area_hectares(
            np.ones((10, 10), dtype=bool),
            pixel_size_m=(10.0, 10.0),
            crs="EPSG:4326",
            derived_from=[scene_pre],
            code_version="0.1.0",
        )


def test_area_hectares_refuses_empty_provenance() -> None:
    with pytest.raises(ValueError, match="derived_from is empty"):
        area_hectares(
            np.ones((10, 10), dtype=bool),
            pixel_size_m=(10.0, 10.0),
            crs="EPSG:32643",
            derived_from=[],
            code_version="0.1.0",
        )


def test_area_hectares_refuses_non_2d_mask(scene_pre: SceneRef) -> None:
    with pytest.raises(ValueError, match="2-D"):
        area_hectares(
            np.ones((2, 10, 10), dtype=bool),
            pixel_size_m=(10.0, 10.0),
            crs="EPSG:32643",
            derived_from=[scene_pre],
            code_version="0.1.0",
        )


def test_empty_mask_measures_zero_not_nothing(scene_pre: SceneRef) -> None:
    """Zero hectares is a real answer and must be expressible.

    Distinct from an abstention: 'we measured, and found no water' is different
    from 'we could not measure'. Both must be representable, and they must not be
    confusable.
    """
    measurement = area_hectares(
        np.zeros((10, 10), dtype=bool),
        pixel_size_m=(10.0, 10.0),
        crs="EPSG:32643",
        derived_from=[scene_pre],
        code_version="0.1.0",
    )
    assert measurement.value == Decimal("0.0")
