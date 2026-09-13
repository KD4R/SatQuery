"""Preflight validation: raster spec assertions and no-data accounting."""

from __future__ import annotations

import numpy as np
import pytest

from ml.contracts.scene import (
    BackscatterScale,
    Polarization,
    RasterSpec,
)
from ml.io.preflight import (
    PreflightError,
    validate_against_spec,
    validate_finite_fraction,
)

# CI selects tests by marker (`pytest -m unit`); an unmarked test never runs.
# Everything in this module is a fast, offline, no-I/O unit test.
pytestmark = pytest.mark.unit


def _spec(**overrides: object) -> RasterSpec:
    """Build a valid spec with targeted overrides, to keep each test to one variable."""
    base: dict[str, object] = {
        "band_order": (Polarization.VV, Polarization.VH),
        "scale": BackscatterScale.DECIBEL,
        "dtype": "float32",
        "crs": "EPSG:32643",
        "width": 4,
        "height": 4,
        "pixel_size_m": (10.0, 10.0),
        "nodata": None,
    }
    base.update(overrides)
    return RasterSpec(**base)  # type: ignore[arg-type]


def test_matching_array_and_spec_passes(utm_spec: RasterSpec) -> None:
    spec = _spec()
    array = np.zeros((2, 4, 4), dtype=np.float32)
    validate_against_spec(array, spec, spec)  # must not raise


def test_band_count_mismatch_is_refused() -> None:
    spec = _spec()
    array = np.zeros((1, 4, 4), dtype=np.float32)  # spec declares 2 bands
    with pytest.raises(PreflightError, match="band_order has 2 bands"):
        validate_against_spec(array, spec, spec)


def test_dimension_mismatch_is_refused() -> None:
    spec = _spec()
    array = np.zeros((2, 4, 8), dtype=np.float32)
    with pytest.raises(PreflightError, match="declared dimensions"):
        validate_against_spec(array, spec, spec)


def test_dtype_mismatch_is_refused() -> None:
    spec = _spec()
    array = np.zeros((2, 4, 4), dtype=np.float64)
    with pytest.raises(PreflightError, match="dtype"):
        validate_against_spec(array, spec, spec)


def test_band_order_mismatch_is_refused_with_an_explanatory_message() -> None:
    """The Sen1Floods11 VH/VV versus model VV/VH trap.

    The message names the trap explicitly, because someone hitting this at 2am
    needs to know it is a reorder rather than a corrupt file.
    """
    source = _spec(band_order=(Polarization.VH, Polarization.VV))  # file order
    model = _spec(band_order=(Polarization.VV, Polarization.VH))  # model order
    array = np.zeros((2, 4, 4), dtype=np.float32)

    with pytest.raises(PreflightError, match="band order mismatch"):
        validate_against_spec(array, source, model)


def test_crs_mismatch_is_refused() -> None:
    source = _spec(crs="EPSG:4326")
    model = _spec(crs="EPSG:32643")
    array = np.zeros((2, 4, 4), dtype=np.float32)
    with pytest.raises(PreflightError, match="CRS mismatch"):
        validate_against_spec(array, source, model)


def test_scale_difference_is_allowed_because_conversion_is_legitimate() -> None:
    """Converting power to dB is a real, logged step -- not a validation failure."""
    source = _spec(scale=BackscatterScale.POWER)
    model = _spec(scale=BackscatterScale.DECIBEL)
    array = np.zeros((2, 4, 4), dtype=np.float32)
    validate_against_spec(array, source, model)  # must not raise


def test_two_dimensional_array_is_refused() -> None:
    spec = _spec()
    with pytest.raises(PreflightError, match="3-D"):
        validate_against_spec(np.zeros((4, 4), dtype=np.float32), spec, spec)


def test_mostly_nodata_raster_is_refused() -> None:
    """An area measured from a sliver would describe the whole AOI wrongly."""
    array = np.full((10, 10), np.nan, dtype=np.float32)
    array[0, :] = 1.0  # 10% finite
    with pytest.raises(PreflightError, match="valid"):
        validate_finite_fraction(array, minimum=0.5)


def test_finite_fraction_is_returned_for_recording_as_a_caveat() -> None:
    array = np.full((10, 10), 1.0, dtype=np.float32)
    array[0, :] = np.nan  # 90% finite
    assert validate_finite_fraction(array, minimum=0.5) == pytest.approx(0.9)


def test_empty_raster_is_refused() -> None:
    with pytest.raises(PreflightError, match="empty"):
        validate_finite_fraction(np.array([], dtype=np.float32))
