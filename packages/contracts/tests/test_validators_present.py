"""Every validator in packages/contracts/ml.py, proved to still refuse.

ADR-0007 D17.

These are not ordinary contract tests. They exist because the validators were
lost once, in transcription, and nothing noticed: the models kept the strict
*config* -- frozen, extra="forbid", revalidate_instances="always" -- and lost the
strict *behaviour*. A file that looks that careful and validates nothing is worse
than one that never claimed to, because reviewers stop reading it.

What got through, measured against the file before the restore: hectares in
EPSG:4326, a negative area, and a NOT_CALIBRATED confidence carrying 0.9. Each is
a plausible wrong number arriving with full provenance attached, which makes it
read as more credible rather than less.

Two rules, both learned the hard way while writing this file
------------------------------------------------------------
**Every test asserts on the error message, not just that a ValidationError was
raised.** The first version of this probe passed seven of seven while testing
nothing: the objects were missing required fields, pydantic raised for that
reason, and the `except ValidationError` swallowed it as a pass.

**Every builder is exercised unmodified first.** `valid_measurement()` and
`valid_confidence()` are constructed at import time below, so if the happy path
ever stops constructing, this module fails at collection rather than reporting a
suite of green false negatives.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.contracts import (
    PHYSICAL_UNITS,
    BackscatterScale,
    Confidence,
    ConfidenceBasis,
    Measurement,
    MeasurementUnit,
    PassDirection,
    Polarization,
    Provider,
    RasterSpec,
    ScenePair,
    SceneRef,
)

pytestmark = pytest.mark.contract

EARLIER = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 1, 13, tzinfo=timezone.utc)


def scene(
    *,
    orbit: int | None = 1,
    direction: PassDirection | None = PassDirection.ASCENDING,
    acquired_at: datetime = EARLIER,
) -> SceneRef:
    return SceneRef(
        provider=Provider.SEN1FLOODS11,
        collection="sen1floods11",
        item_id=f"chip-{acquired_at.day}",
        acquired_at=acquired_at,
        platform="S1A",
        instrument="IW",
        relative_orbit=orbit,
        pass_direction=direction,
        href="https://example.invalid/chip.tif",
    )


def measurement(**over: object) -> Measurement:
    fields: dict[str, object] = dict(
        name="flooded_area",
        value=Decimal("12.5"),
        unit=MeasurementUnit.HECTARES,
        produced_by="otsu-single-date",
        code_version="0.2.0",
        crs="EPSG:32643",
        derived_from=(scene(),),
    )
    fields.update(over)
    return Measurement(**fields)  # type: ignore[arg-type]


def confidence(**over: object) -> Confidence:
    fields: dict[str, object] = dict(
        basis=ConfidenceBasis.NOT_CALIBRATED,
        value=None,
        interval=None,
        calibration_ref=None,
        agreement_iou=None,
        caveats=(),
    )
    fields.update(over)
    return Confidence(**fields)  # type: ignore[arg-type]


def raster_spec(**over: object) -> RasterSpec:
    fields: dict[str, object] = dict(
        band_order=(Polarization.VV, Polarization.VH),
        scale=BackscatterScale.DECIBEL,
        dtype="float32",
        crs="EPSG:32643",
        width=512,
        height=512,
        pixel_size_m=(10.0, 10.0),
        nodata=None,
    )
    fields.update(over)
    return RasterSpec(**fields)  # type: ignore[arg-type]


# Import-time positive controls. If a builder stops constructing, every test below
# would "pass" for the wrong reason, so fail loudly here instead.
measurement()
confidence()
raster_spec()
ScenePair(pre=scene(), post=scene(acquired_at=LATER))


def refuses(builder, expected: str) -> None:
    """Assert the model refuses *for the stated reason*.

    The message check is the whole point. A bare `pytest.raises(ValidationError)`
    is satisfied by a typo in the test's own keyword arguments.
    """
    with pytest.raises(ValidationError) as caught:
        builder()
    assert expected in str(caught.value), (
        f"refused, but not for the expected reason.\n  wanted: {expected!r}\n"
        f"  got: {caught.value}"
    )


# --- Measurement ----------------------------------------------------------- #


@pytest.mark.parametrize("crs", ["EPSG:4326", "EPSG:4258", "not-a-crs"])
def test_a_physical_extent_cannot_be_measured_in_a_geographic_crs(crs: str) -> None:
    """The single most important guard in the file, and one of the three lost.

    EPSG:4258 is in here on purpose: an earlier blacklist-shaped version of this
    check listed five geographic identifiers and let ETRS89 through.
    """
    refuses(lambda: measurement(crs=crs), "not safe to measure in")


def test_epsg_3857_is_projected_and_still_refused() -> None:
    """Projected is not the same question as area-safe.

    Web Mercator has linear units, so an `is_projected` check passes it, and the
    area it yields is inflated by 1/cos^2(latitude) -- roughly double at 45 deg.
    Nothing raises and the number looks ordinary.
    """
    refuses(lambda: measurement(crs="EPSG:3857"), "not safe to measure in")


#: Hardcoded on purpose. Deriving this from PHYSICAL_UNITS would make the test
#: restate the implementation and pass no matter what the implementation said.
EXPECTED_PHYSICAL_UNITS: tuple[MeasurementUnit, ...] = (
    MeasurementUnit.HECTARES,
    MeasurementUnit.SQUARE_KILOMETRES,
    MeasurementUnit.METRES,
    MeasurementUnit.KILOMETRES,
)


def test_physical_units_membership_is_exactly_what_the_guard_needs() -> None:
    """Dropping a unit from PHYSICAL_UNITS silently disables the guard for it.

    The contract still looks strict -- the validator is still there, still runs,
    still refuses things -- and hectares in EPSG:4326 quietly start constructing
    again. This is the invariant that would otherwise argue for fingerprinting
    packages/contracts/ml.py into the P3-15 report gate; pinning it here costs
    nothing to satisfy instead of a 400-chip regeneration per docstring edit.
    """
    assert set(PHYSICAL_UNITS) == set(EXPECTED_PHYSICAL_UNITS)


@pytest.mark.parametrize("unit", EXPECTED_PHYSICAL_UNITS)
def test_every_physical_unit_is_covered_by_the_guard(unit: MeasurementUnit) -> None:
    """Each unit individually, not just hectares."""
    refuses(lambda: measurement(unit=unit, crs="EPSG:4326"), "not safe to measure in")


def test_dimensionless_units_are_not_subject_to_the_crs_guard() -> None:
    """A count is a count wherever it was taken; over-refusing is its own bug."""
    assert measurement(unit=MeasurementUnit.COUNT, value=Decimal(3), crs="EPSG:4326").value == 3


@pytest.mark.parametrize("unit", [MeasurementUnit.HECTARES, MeasurementUnit.COUNT])
def test_a_negative_area_or_count_is_refused(unit: MeasurementUnit) -> None:
    """COUNT included deliberately: a count of detections cannot be negative either."""
    refuses(lambda: measurement(unit=unit, value=Decimal("-1")), "negative value")


@pytest.mark.parametrize("value", ["-0.1", "1.5", "42"])
def test_a_fraction_outside_zero_to_one_is_refused(value: str) -> None:
    refuses(
        lambda: measurement(unit=MeasurementUnit.FRACTION, value=Decimal(value)),
        "fractions lie in",
    )


def test_a_measurement_must_name_the_scenes_it_came_from() -> None:
    refuses(lambda: measurement(derived_from=()), "at least 1 item")


# --- Confidence ------------------------------------------------------------ #


def test_not_calibrated_must_not_carry_a_value() -> None:
    """The third of the three that got through. An unjustified 0.9 is worse than
    no number, because the UI has no way to tell them apart."""
    refuses(lambda: confidence(value=Decimal("0.9")), "NOT_CALIBRATED but a value")


def test_a_basis_other_than_not_calibrated_must_carry_a_value() -> None:
    refuses(
        lambda: confidence(basis=ConfidenceBasis.CALIBRATED_PROBABILITY, calibration_ref="r"),
        "no value was supplied",
    )


def test_calibrated_probability_must_cite_its_calibration_report() -> None:
    refuses(
        lambda: confidence(basis=ConfidenceBasis.CALIBRATED_PROBABILITY, value=Decimal("0.9")),
        "requires calibration_ref",
    )


def test_model_agreement_must_report_the_agreement() -> None:
    refuses(
        lambda: confidence(basis=ConfidenceBasis.MODEL_AGREEMENT, value=Decimal("0.9")),
        "agreement_iou is None",
    )


def test_model_agreement_value_must_equal_the_agreement_it_reports() -> None:
    """Each field was individually legal; together they contradicted each other."""
    refuses(
        lambda: confidence(
            basis=ConfidenceBasis.MODEL_AGREEMENT,
            value=Decimal("0.9"),
            agreement_iou=Decimal("0.5"),
        ),
        "differ",
    )


def test_a_value_outside_its_own_interval_is_refused() -> None:
    refuses(
        lambda: confidence(
            basis=ConfidenceBasis.CALIBRATED_PROBABILITY,
            value=Decimal("0.9"),
            calibration_ref="reports/calibration.md",
            interval=(Decimal("0.1"), Decimal("0.5")),
        ),
        "outside its own interval",
    )


@pytest.mark.parametrize("field", ["value", "agreement_iou"])
def test_probabilities_are_bounded(field: str) -> None:
    refuses(
        lambda: confidence(
            basis=ConfidenceBasis.MODEL_AGREEMENT,
            **{
                field: Decimal("1.5"),
                "value" if field == "agreement_iou" else "agreement_iou": Decimal("1.5"),
            },
        ),
        "must lie in [0, 1]",
    )


def test_an_inverted_interval_is_refused() -> None:
    refuses(
        lambda: confidence(
            basis=ConfidenceBasis.CALIBRATED_PROBABILITY,
            value=Decimal("0.4"),
            calibration_ref="reports/calibration.md",
            interval=(Decimal("0.8"), Decimal("0.2")),
        ),
        "low <= high",
    )


def test_not_calibrated_helper_produces_a_valid_object() -> None:
    honest = Confidence.not_calibrated(caveats=("model output is uncalibrated",))
    assert honest.basis is ConfidenceBasis.NOT_CALIBRATED
    assert honest.value is None
    assert honest.caveats == ("model output is uncalibrated",)


# --- RasterSpec and ScenePair ---------------------------------------------- #


def test_a_duplicated_band_is_refused() -> None:
    refuses(
        lambda: raster_spec(band_order=(Polarization.VV, Polarization.VV)),
        "duplicates",
    )


@pytest.mark.parametrize("size", [(0.0, 10.0), (10.0, 0.0), (-10.0, 10.0)])
def test_a_nonpositive_pixel_size_is_refused(size: tuple[float, float]) -> None:
    """A negative y step is normal in a GeoTIFF transform and must be abs()'d
    before it reaches here; left signed it yields a negative area."""
    refuses(lambda: raster_spec(pixel_size_m=size), "positive magnitudes")


@pytest.mark.parametrize(
    "pre_kwargs, post_kwargs, expected",
    [
        ({"orbit": 1}, {"orbit": 2}, "relative_orbit mismatch"),
        ({"orbit": None}, {"orbit": 1}, "unknown relative_orbit"),
        ({}, {"direction": PassDirection.DESCENDING}, "pass_direction mismatch"),
        ({}, {"direction": None}, "unknown pass_direction"),
    ],
)
def test_scenes_of_incomparable_geometry_cannot_be_paired(
    pre_kwargs: dict, post_kwargs: dict, expected: str
) -> None:
    """Sentinel-1 looks sideways, so a mismatched pair measures viewing angle as
    well as ground change -- not a noisy answer, a measurement of the wrong thing."""
    refuses(
        lambda: ScenePair(
            pre=scene(**pre_kwargs),
            post=scene(acquired_at=LATER, **post_kwargs),
        ),
        expected,
    )


def test_a_reversed_pair_is_refused() -> None:
    """Swapping pre and post inverts the log-ratio, turning a flood into a drying
    event -- a plausible-looking wrong answer rather than an error."""
    refuses(
        lambda: ScenePair(pre=scene(acquired_at=LATER), post=scene(acquired_at=EARLIER)),
        "strictly before",
    )


def test_a_comparable_pair_still_constructs() -> None:
    pair = ScenePair(pre=scene(), post=scene(acquired_at=LATER))
    assert pair.pre.acquired_at < pair.post.acquired_at
