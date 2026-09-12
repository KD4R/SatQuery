"""Confidence, with a declared basis or not at all.

Why a plain float is not acceptable
-----------------------------------
The P3 specification shows ``"confidence": 0.94`` without saying where the number
comes from. That is the sharpest question a reviewer can ask, because a confidence
figure *is itself a number* -- and the whole premise of this subsystem is that a
number must be earned.

There are exactly three defensible sources, and this module makes the caller
declare which one is in play:

``MODEL_AGREEMENT``
    Two independent methods -- the deterministic Otsu baseline and the learned
    model -- were run on the same input and their masks compared. The reported
    value is derived from their agreement (IoU). This is stronger evidence than a
    softmax because it is disagreement between independent methods rather than one
    model's opinion of itself, and it is available from day one because the
    baseline needs no training.

``CALIBRATED_PROBABILITY``
    A post-hoc calibration (temperature scaling or isotonic regression) was fitted
    on a held-out *validation* split -- never the test split -- and the resulting
    probabilities were checked with Expected Calibration Error and a reliability
    diagram. Only then does 0.87 mean "predictions in this bin were correct 87% of
    the time". Calibration is configuration-specific: a model calibrated on
    Sen1Floods11 is *not* calibrated for a different sensor, resolution or
    incidence angle, so a value may only be reported inside the configuration it
    was fitted for.

    Reference: Guo, Pleiss, Sun, Weinberger (2017), "On Calibration of Modern
    Neural Networks", arXiv:1706.04599.

``NOT_CALIBRATED``
    Neither of the above applies. ``value`` must then be ``None``. An honest null
    beats a decorative float, and the UI is expected to render it as
    "not calibrated for this configuration" rather than hiding the field.

A raw softmax output is explicitly *not* one of the three. A softmax is a
normalised score, not a probability, and presenting it as one is the same class of
defect as a fabricated hectare figure.
"""

from __future__ import annotations

from collections.abc import Sequence

from decimal import Decimal
from enum import Enum

from pydantic import model_validator

from ml.contracts.base import Strict


class ConfidenceBasis(str, Enum):
    """What kind of evidence backs a confidence value."""

    MODEL_AGREEMENT = "model_agreement"
    CALIBRATED_PROBABILITY = "calibrated_probability"
    NOT_CALIBRATED = "not_calibrated"


class Confidence(Strict):
    """A confidence value together with the evidence that justifies it.

    Parameters
    ----------
    basis
        Which of the three sources produced this. The UI renders each differently
        because they mean different things.
    value
        The confidence in [0, 1], or ``None`` when ``basis`` is ``NOT_CALIBRATED``.
    interval
        Optional (low, high) bounds, when the method produces them.
    calibration_ref
        Pointer to the generated calibration report, e.g.
        ``"reports/calibration_2026-10.md#s1-rtc-vv-vh"``. Mandatory for
        ``CALIBRATED_PROBABILITY`` -- a calibrated number that cannot cite its
        calibration is not calibrated, it is asserted.
    agreement_iou
        Intersection-over-union between the deterministic baseline mask and the
        learned model mask, when both were run.
    caveats
        Human-readable flags from the physical plausibility checks, e.g.
        ``"4% of AOI in radar shadow"``. These are frequently more convincing to a
        domain expert than any probability, so they are first-class rather than
        buried in a log.
    """

    basis: ConfidenceBasis
    value: Decimal | None
    interval: tuple[Decimal, Decimal] | None
    calibration_ref: str | None
    agreement_iou: Decimal | None
    caveats: tuple[str, ...]

    @model_validator(mode="after")
    def _value_requires_a_basis(self) -> Confidence:
        """``NOT_CALIBRATED`` means we do not have a number, so we must not print one."""
        if self.basis is ConfidenceBasis.NOT_CALIBRATED and self.value is not None:
            raise ValueError(
                "basis is NOT_CALIBRATED but a value was supplied; "
                "report None and let the UI say so, rather than printing an "
                "unjustified figure"
            )
        if self.basis is not ConfidenceBasis.NOT_CALIBRATED and self.value is None:
            raise ValueError(
                f"basis is {self.basis.value} but no value was supplied; "
                "either provide the value or declare NOT_CALIBRATED"
            )
        return self

    @model_validator(mode="after")
    def _calibrated_must_cite_its_calibration(self) -> Confidence:
        """A calibrated probability that cannot point at its report is not calibrated."""
        if self.basis is ConfidenceBasis.CALIBRATED_PROBABILITY and not self.calibration_ref:
            raise ValueError(
                "CALIBRATED_PROBABILITY requires calibration_ref pointing at the "
                "generated calibration report (ECE + reliability diagram)"
            )
        return self

    @model_validator(mode="after")
    def _agreement_basis_requires_agreement(self) -> Confidence:
        """A MODEL_AGREEMENT confidence must actually carry the agreement it claims."""
        if self.basis is ConfidenceBasis.MODEL_AGREEMENT and self.agreement_iou is None:
            raise ValueError(
                "basis is MODEL_AGREEMENT but agreement_iou is None; the agreement "
                "between the deterministic baseline and the learned model is the "
                "evidence, so it must be reported"
            )
        return self

    @model_validator(mode="after")
    def _bound_values(self) -> Confidence:
        """Confidences and IoUs are both in [0, 1]; anything else is a bug upstream."""
        for label, candidate in (
            ("value", self.value),
            ("agreement_iou", self.agreement_iou),
        ):
            if candidate is not None and not (Decimal(0) <= candidate <= Decimal(1)):
                raise ValueError(f"{label} must lie in [0, 1], got {candidate}")
        if self.interval is not None:
            low, high = self.interval
            if not (Decimal(0) <= low <= high <= Decimal(1)):
                raise ValueError(
                    f"interval must satisfy 0 <= low <= high <= 1, got {self.interval}"
                )
        return self

    @model_validator(mode="after")
    def _fields_must_not_contradict_each_other(self) -> Confidence:
        """Bound each field, then check they are telling the same story.

        Bounding fields independently is not enough. Every field below was already
        individually legal in an object that, read as a whole, contradicts itself:

        * ``basis=MODEL_AGREEMENT, value=0.9, agreement_iou=0.5`` -- the basis says
          the confidence *is* the agreement between two independent methods, and
          then reports a different number. A reader has no way to know which one
          the pipeline acted on.
        * ``value=0.9, interval=(0.1, 0.4)`` -- an interval that excludes its own
          point estimate. Rendered in a report this is not merely wrong, it is
          incoherent, and it survives review because both halves look reasonable
          on their own.

        Consistency between fields is part of the contract, so it is checked at
        construction like everything else.
        """
        if (
            self.basis is ConfidenceBasis.MODEL_AGREEMENT
            and self.value is not None
            and self.agreement_iou is not None
            and self.value != self.agreement_iou
        ):
            raise ValueError(
                f"basis is MODEL_AGREEMENT so value is the agreement, but value "
                f"({self.value}) and agreement_iou ({self.agreement_iou}) differ. "
                "Report the IoU as the value, or choose a different basis."
            )

        if self.value is not None and self.interval is not None:
            low, high = self.interval
            if not (low <= self.value <= high):
                raise ValueError(
                    f"value {self.value} lies outside its own interval " f"[{low}, {high}]"
                )
        return self

    @classmethod
    def not_calibrated(cls, *, caveats: Sequence[str] | None = None) -> Confidence:
        """Convenience constructor for the honest-null case.

        Used wherever a model runs outside the configuration it was calibrated for.
        """
        return cls(
            basis=ConfidenceBasis.NOT_CALIBRATED,
            value=None,
            interval=None,
            calibration_ref=None,
            agreement_iou=None,
            caveats=tuple(caveats or ()),
        )
