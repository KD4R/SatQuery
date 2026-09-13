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

import pytest
from pydantic import ValidationError

from packages.contracts import Confidence, ConfidenceBasis, Measurement, MeasurementUnit

pytestmark = pytest.mark.unit


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


def test_negative_count_is_refused(scene_pre) -> None:
    """COUNT sat outside the negativity check because the check was named for extents.

    A count of pixels, scenes or detections is no more able to be negative than an
    area is. Because a validated ``Measurement`` travels straight into an
    ``Analysis`` and out to the user, an impossible value arrives carrying full
    provenance -- which makes it read as more credible, not less.
    """
    with pytest.raises(ValidationError, match="negative value"):
        Measurement(
            name="water_pixels",
            value=Decimal("-1"),
            unit=MeasurementUnit.COUNT,
            produced_by="test",
            code_version="0.0.0",
            crs="EPSG:32643",
            derived_from=(scene_pre,),
        )


def test_zero_count_is_still_allowed(scene_pre) -> None:
    """Zero detections is a real, reportable result and must not be caught."""
    measurement = Measurement(
        name="water_pixels",
        value=Decimal("0"),
        unit=MeasurementUnit.COUNT,
        produced_by="test",
        code_version="0.0.0",
        crs="EPSG:32643",
        derived_from=(scene_pre,),
    )
    assert measurement.value == Decimal("0")
