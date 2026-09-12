"""Regression tests for the defects found in review of the foundation commit.

Every test here corresponds to a specific finding on PR #10. They live in one
module, rather than being scattered into the topic modules, because their shared
property is what makes them worth keeping: **each one passed silently before the
fix.** Not one produced an exception, a warning or a visibly odd value. They
produced plausible wrong numbers, which is the failure mode this subsystem is
built to prevent, and they got past a reviewer who had just written a README
listing four traps of exactly this kind.

Reference: https://github.com/KD4R/SatQuery/pull/10
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest
from pydantic import ValidationError

from ml.contracts.confidence import Confidence, ConfidenceBasis
from ml.contracts.measurement import Measurement, MeasurementUnit
from ml.crs_policy import is_area_safe, is_projected
from ml.evaluation.segmentation import confusion
from ml.geo.area import pixel_area_m2
from ml.geo.crs import CRSError, assert_area_safe
from ml.preflight.raster import ALLOWED_SCHEMES, validate_finite_fraction
from ml.sar.units import amplitude_to_db

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# Web Mercator is projected, and is not safe for area                          #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# The CRS check must be an allowlist, not a blacklist                          #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Non-finite pixel dimensions                                                  #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Amplitude is a magnitude                                                     #
# --------------------------------------------------------------------------- #


def test_negative_amplitude_becomes_nan_not_zero_db() -> None:
    """Squaring laundered invalid samples into plausible backscatter.

    Amplitude is by definition non-negative, so ``-1`` is corrupt or mis-scaled.
    Squaring first turns it into ``1``, which converts to a clean ``0 dB`` -- a
    value in the middle of the plausible range for a bright urban scatterer. The
    invalid pixel then contributes to the Otsu histogram as though it were an
    observation.
    """
    out = amplitude_to_db(np.array([-1.0, -0.5, 0.0, 2.0]))
    assert np.isnan(out[0])
    assert np.isnan(out[1])
    assert np.isnan(out[2])  # zero amplitude is also unmeasurable, matching power_to_db
    assert np.isclose(out[3], 20.0 * np.log10(2.0))


def test_valid_amplitude_is_unchanged_by_the_guard() -> None:
    amplitudes = np.array([0.5, 1.0, 3.0, 10.0])
    assert np.allclose(amplitude_to_db(amplitudes), 20.0 * np.log10(amplitudes))


# --------------------------------------------------------------------------- #
# Predictions get the same label validation as truth                           #
# --------------------------------------------------------------------------- #


def test_prediction_with_a_class_id_is_refused() -> None:
    """The asymmetry that made the truth-side guard only half a guard.

    A model emitting class IDs (0 land, 1 water, 2 cloud) and an argmax taken over
    the wrong axis both produce integer arrays. Casting those to bool scores every
    non-zero entry as water, so class 2 inflates recall and nothing raises. The
    truth side already refused this; the prediction side did not.
    """
    predicted = np.array([[0, 1, 2]], dtype=np.int16)
    truth = np.array([[0, 1, 1]], dtype=np.int16)
    with pytest.raises(ValueError, match="predicted contains values"):
        confusion(predicted, truth, ignore_value=-1)


def test_prediction_of_minus_one_is_refused() -> None:
    predicted = np.array([[-1, 1]], dtype=np.int16)
    truth = np.array([[0, 1]], dtype=np.int16)
    with pytest.raises(ValueError, match="predicted contains values"):
        confusion(predicted, truth, ignore_value=-999)


def test_boolean_and_zero_one_predictions_are_both_accepted() -> None:
    truth = np.array([[0, 1, 1, 0]], dtype=np.int16)
    as_bool = confusion(np.array([[False, True, True, False]]), truth, ignore_value=-1)
    as_int = confusion(np.array([[0, 1, 1, 0]], dtype=np.int16), truth, ignore_value=-1)
    assert as_bool == as_int


def test_prediction_validation_ignores_pixels_masked_by_ignore_value() -> None:
    """A stray value under a no-data pixel must not fail the whole chip.

    Those pixels are excluded from every count, so rejecting on their content
    would refuse rasters that score perfectly well.
    """
    predicted = np.array([[7, 1, 0]], dtype=np.int16)
    truth = np.array([[-1, 1, 0]], dtype=np.int16)
    metrics = confusion(predicted, truth, ignore_value=-1)
    assert metrics.ignored_pixels == 1
    assert metrics.true_positive == 1
    assert metrics.true_negative == 1


# --------------------------------------------------------------------------- #
# F1 of an entirely wrong prediction is zero, not NaN                          #
# --------------------------------------------------------------------------- #


def test_f1_is_zero_when_the_prediction_is_entirely_wrong() -> None:
    """NaN here silently deleted the worst samples from any average.

    Precision and recall are both defined and both 0 -- there were water pixels,
    and none were found. F1 is 0. Returning NaN meant a mean over chips skipped
    exactly the failures the evaluation exists to surface, and IoU already
    returned 0.0 for this case, so the two metrics disagreed.
    """
    predicted = np.array([[1, 0]], dtype=np.int16)
    truth = np.array([[0, 1]], dtype=np.int16)
    metrics = confusion(predicted, truth, ignore_value=-1)

    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.intersection_over_union == 0.0


def test_f1_stays_nan_when_the_positive_class_is_genuinely_absent() -> None:
    """The case NaN is *right* for, which the fix must not break.

    No water in the truth and none predicted: recall is 0/0. There is nothing to
    score, which is different from scoring zero, and averaging a 0.0 in here would
    understate performance rather than overstate it.
    """
    predicted = np.array([[0, 0]], dtype=np.int16)
    truth = np.array([[0, 0]], dtype=np.int16)
    metrics = confusion(predicted, truth, ignore_value=-1)
    assert np.isnan(metrics.recall)
    assert np.isnan(metrics.f1)


# --------------------------------------------------------------------------- #
# Finite no-data sentinels                                                     #
# --------------------------------------------------------------------------- #


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


def test_nan_nodata_still_works_when_a_sentinel_is_also_declared() -> None:
    array = np.full((10, 10), np.nan)
    array[:8, :] = -12.0
    assert validate_finite_fraction(array, minimum=0.5, nodata=-9999.0) == pytest.approx(0.8)


# --------------------------------------------------------------------------- #
# The advertised-but-unreachable s3 scheme                                     #
# --------------------------------------------------------------------------- #


def test_s3_is_no_longer_advertised() -> None:
    """It never worked: in ``s3://bucket/key`` the bucket sits in the host
    position, so the host check compared a bucket name against HTTPS hostnames and
    rejected every such URL. A capability that always fails is worse than an
    absent one, because a caller builds against it.
    """
    assert "s3" not in ALLOWED_SCHEMES
    assert ALLOWED_SCHEMES == frozenset({"https"})


# --------------------------------------------------------------------------- #
# Contract fields cannot be mutated after validation                           #
# --------------------------------------------------------------------------- #


def test_provenance_cannot_be_mutated_after_validation(scene_pre) -> None:
    """``frozen=True`` blocks reassignment, not in-place mutation of a list.

    ``derived_from`` was a ``list``, so a caller holding the object could append or
    clear it after validation and change the provenance of a measurement that had
    already been checked -- defeating the entire reason for attaching it. This is
    the same argument raised against the mutable shared ``SceneRef`` in issue #12,
    and it applied here too.
    """
    measurement = Measurement(
        name="inundated_area",
        value=Decimal("12.5"),
        unit=MeasurementUnit.HECTARES,
        produced_by="test",
        code_version="0.0.0",
        crs="EPSG:32643",
        derived_from=(scene_pre,),
    )
    assert isinstance(measurement.derived_from, tuple)
    with pytest.raises(AttributeError):
        measurement.derived_from.append(scene_pre)  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# Confidence fields must agree with each other                                 #
# --------------------------------------------------------------------------- #


def test_agreement_confidence_may_not_contradict_its_own_iou() -> None:
    """Each field was individually legal; together they said two different things.

    ``MODEL_AGREEMENT`` means the confidence *is* the agreement between two
    independent methods. Reporting 0.9 beside an IoU of 0.5 leaves a reader with no
    way to know which number the pipeline acted on.
    """
    with pytest.raises(ValidationError, match="agreement_iou"):
        Confidence(
            basis=ConfidenceBasis.MODEL_AGREEMENT,
            value=Decimal("0.9"),
            interval=None,
            calibration_ref=None,
            agreement_iou=Decimal("0.5"),
            caveats=(),
        )


def test_agreement_confidence_accepts_a_consistent_pair() -> None:
    confidence = Confidence(
        basis=ConfidenceBasis.MODEL_AGREEMENT,
        value=Decimal("0.72"),
        interval=None,
        calibration_ref=None,
        agreement_iou=Decimal("0.72"),
        caveats=(),
    )
    assert confidence.value == confidence.agreement_iou


def test_interval_may_not_exclude_its_own_point_estimate() -> None:
    """Incoherent rather than merely wrong, and it survives review because both
    halves look reasonable in isolation."""
    with pytest.raises(ValidationError, match="outside its own interval"):
        Confidence(
            basis=ConfidenceBasis.CALIBRATED_PROBABILITY,
            value=Decimal("0.9"),
            interval=(Decimal("0.1"), Decimal("0.4")),
            calibration_ref="reports/calibration_2026-10.md",
            agreement_iou=None,
            caveats=(),
        )


def test_interval_containing_the_value_is_accepted() -> None:
    confidence = Confidence(
        basis=ConfidenceBasis.CALIBRATED_PROBABILITY,
        value=Decimal("0.82"),
        interval=(Decimal("0.75"), Decimal("0.88")),
        calibration_ref="reports/calibration_2026-10.md",
        agreement_iou=None,
        caveats=(),
    )
    assert confidence.interval is not None
