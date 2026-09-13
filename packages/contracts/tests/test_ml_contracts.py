"""Contract rejection tests.

Every test here asserts that an *invalid* object cannot be constructed. That is the
point of the contracts package: the failure should happen at the boundary, loudly,
rather than becoming a wrong number several stages later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.contracts import (
    Abstention,
    AbstentionReason,
    Analysis,
    BackscatterScale,
    Confidence,
    ConfidenceBasis,
    Measurement,
    MeasurementUnit,
    PassDirection,
    Polarization,
    RasterSpec,
    ScenePair,
    SceneRef,
)

# CI selects tests by marker (`pytest -m unit`); an unmarked test never runs.
# Everything in this module is a fast, offline, no-I/O unit test.
pytestmark = pytest.mark.unit

# --------------------------------------------------------------------------- #
# Measurement                                                                  #
# --------------------------------------------------------------------------- #


def test_measurement_rejects_hectares_in_geographic_crs(scene_pre: SceneRef) -> None:
    """The single most common geospatial defect must be impossible to express."""
    with pytest.raises(ValidationError, match="geographic"):
        Measurement(
            name="inundated_area",
            value=Decimal("4127.6"),
            unit=MeasurementUnit.HECTARES,
            produced_by="ml.geo.area.area_hectares",
            code_version="0.1.0",
            crs="EPSG:4326",  # <- degrees, not metres
            derived_from=(scene_pre,),
        )


def test_measurement_allows_dimensionless_units_in_geographic_crs(
    scene_pre: SceneRef,
) -> None:
    """A count has no units, so the CRS guard must not fire on it."""
    measurement = Measurement(
        name="polygon_count",
        value=Decimal("12"),
        unit=MeasurementUnit.COUNT,
        produced_by="ml.geo.area.area_hectares",
        code_version="0.1.0",
        crs="EPSG:4326",
        derived_from=(scene_pre,),
    )
    assert measurement.value == Decimal("12")


def test_measurement_requires_provenance() -> None:
    """A measurement that cannot say where it came from is not a measurement."""
    with pytest.raises(ValidationError):
        Measurement(
            name="inundated_area",
            value=Decimal("1.0"),
            unit=MeasurementUnit.HECTARES,
            produced_by="ml.geo.area.area_hectares",
            code_version="0.1.0",
            crs="EPSG:32643",
            derived_from=(),  # <- min_length=1
        )


def test_measurement_is_frozen(scene_pre: SceneRef) -> None:
    """Provenance attached at construction must not be replaceable afterwards."""
    measurement = Measurement(
        name="inundated_area",
        value=Decimal("10.0"),
        unit=MeasurementUnit.HECTARES,
        produced_by="ml.geo.area.area_hectares",
        code_version="0.1.0",
        crs="EPSG:32643",
        derived_from=(scene_pre,),
    )
    with pytest.raises(ValidationError):
        measurement.value = Decimal("99999.0")  # type: ignore[misc]


def test_measurement_rejects_unknown_field(scene_pre: SceneRef) -> None:
    """extra="forbid": an unexpected field is an error, not silently dropped."""
    with pytest.raises(ValidationError):
        Measurement(
            name="inundated_area",
            value=Decimal("10.0"),
            unit=MeasurementUnit.HECTARES,
            produced_by="p",
            code_version="0.1.0",
            crs="EPSG:32643",
            derived_from=(scene_pre,),
            confidence=0.94,  # type: ignore[call-arg]  # <- not a field here
        )


def test_measurement_rejects_out_of_range_fraction(scene_pre: SceneRef) -> None:
    """A fraction above 1 means a denominator went wrong upstream."""
    with pytest.raises(ValidationError, match=r"\[0, 1\]"):
        Measurement(
            name="water_fraction",
            value=Decimal("1.4"),
            unit=MeasurementUnit.FRACTION,
            produced_by="p",
            code_version="0.1.0",
            crs="EPSG:32643",
            derived_from=(scene_pre,),
        )


# --------------------------------------------------------------------------- #
# Confidence                                                                   #
# --------------------------------------------------------------------------- #


def test_confidence_not_calibrated_must_not_carry_a_value() -> None:
    """If we do not have a justified number we must not print one."""
    with pytest.raises(ValidationError, match="NOT_CALIBRATED"):
        Confidence(
            basis=ConfidenceBasis.NOT_CALIBRATED,
            value=Decimal("0.94"),
            interval=None,
            calibration_ref=None,
            agreement_iou=None,
            caveats=(),
        )


def test_confidence_calibrated_must_cite_its_report() -> None:
    """A calibrated probability with nothing to point at is merely asserted."""
    with pytest.raises(ValidationError, match="calibration_ref"):
        Confidence(
            basis=ConfidenceBasis.CALIBRATED_PROBABILITY,
            value=Decimal("0.87"),
            interval=None,
            calibration_ref=None,
            agreement_iou=None,
            caveats=(),
        )


def test_confidence_agreement_basis_must_carry_the_agreement() -> None:
    """MODEL_AGREEMENT without an IoU is a claim with its evidence removed."""
    with pytest.raises(ValidationError, match="agreement_iou"):
        Confidence(
            basis=ConfidenceBasis.MODEL_AGREEMENT,
            value=Decimal("0.9"),
            interval=None,
            calibration_ref=None,
            agreement_iou=None,
            caveats=(),
        )


def test_confidence_not_calibrated_helper_is_valid() -> None:
    """The honest-null path must be easy to construct, or people will fake a number."""
    confidence = Confidence.not_calibrated(caveats=("outside calibrated configuration",))
    assert confidence.value is None
    assert confidence.basis is ConfidenceBasis.NOT_CALIBRATED
    assert confidence.caveats == ("outside calibrated configuration",)


# --------------------------------------------------------------------------- #
# ScenePair -- the orbit rule                                                  #
# --------------------------------------------------------------------------- #


def test_scene_pair_accepts_matching_geometry(scene_pre: SceneRef, scene_post: SceneRef) -> None:
    pair = ScenePair(pre=scene_pre, post=scene_post)
    assert pair.pre.relative_orbit == pair.post.relative_orbit


def test_scene_pair_rejects_orbit_mismatch(scene_pre: SceneRef, scene_post: SceneRef) -> None:
    """Different orbits observe different geometry; the 'change' would be the angle."""
    other_orbit = scene_post.model_copy(update={"relative_orbit": 91})
    with pytest.raises(ValidationError, match="relative_orbit mismatch"):
        ScenePair(pre=scene_pre, post=other_orbit)


def test_scene_pair_rejects_pass_direction_mismatch(
    scene_pre: SceneRef, scene_post: SceneRef
) -> None:
    ascending = scene_post.model_copy(update={"pass_direction": PassDirection.ASCENDING})
    with pytest.raises(ValidationError, match="pass_direction mismatch"):
        ScenePair(pre=scene_pre, post=ascending)


def test_scene_pair_rejects_unknown_orbit(scene_pre: SceneRef, scene_post: SceneRef) -> None:
    """Unknown geometry blocks comparison; it is not assumed to match."""
    unknown = scene_post.model_copy(update={"relative_orbit": None})
    with pytest.raises(ValidationError, match="unknown relative_orbit"):
        ScenePair(pre=scene_pre, post=unknown)


def test_scene_pair_rejects_reversed_chronology(scene_pre: SceneRef, scene_post: SceneRef) -> None:
    """Swapping pre and post inverts the log-ratio, turning a flood into a drying."""
    with pytest.raises(ValidationError, match="strictly before"):
        ScenePair(pre=scene_post, post=scene_pre)


# --------------------------------------------------------------------------- #
# RasterSpec                                                                   #
# --------------------------------------------------------------------------- #


def test_raster_spec_rejects_duplicate_bands() -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        RasterSpec(
            band_order=(Polarization.VV, Polarization.VV),
            scale=BackscatterScale.DECIBEL,
            dtype="float32",
            crs="EPSG:32643",
            width=8,
            height=8,
            pixel_size_m=(10.0, 10.0),
            nodata=None,
        )


def test_raster_spec_rejects_negative_pixel_size() -> None:
    """A north-up affine transform has a negative y step; take abs() before here."""
    with pytest.raises(ValidationError, match="positive magnitudes"):
        RasterSpec(
            band_order=(Polarization.VV,),
            scale=BackscatterScale.DECIBEL,
            dtype="float32",
            crs="EPSG:32643",
            width=8,
            height=8,
            pixel_size_m=(10.0, -10.0),
            nodata=None,
        )


# --------------------------------------------------------------------------- #
# Outcome union                                                                #
# --------------------------------------------------------------------------- #


def test_analysis_requires_at_least_one_measurement_and_scene(
    scene_pre: SceneRef,
) -> None:
    """An 'analysis' that measured nothing is not an analysis."""
    with pytest.raises(ValidationError):
        Analysis(
            measurements=(),
            geometry_ref=None,
            raster_refs=(),
            confidence=None,
            scenes=(scene_pre,),
            degraded_from=None,
            caveats=(),
            trace_id="t-1",
        )


def test_abstention_is_a_value_not_an_exception(scene_pre: SceneRef) -> None:
    """No data is a result the caller can render, with an actionable alternative."""
    abstention = Abstention(
        reason=AbstentionReason.NO_SCENES_IN_WINDOW,
        explanation=("No Sentinel-1 acquisition over this AOI between 12 and 26 August."),
        nearest_usable=datetime(2024, 9, 3, tzinfo=timezone.utc),
        scenes_seen=(scene_pre,),
        trace_id="t-2",
    )
    assert abstention.outcome == "abstained"
    assert abstention.nearest_usable is not None
