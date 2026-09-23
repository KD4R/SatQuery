"""What an analysis may say about its own confidence (P3-11 → serving).

The rule this module enforces is the one in the ``Confidence`` contract: a
confidence *value* may only be printed when there is a calibration that justifies
reading it as a probability. Everything else reports ``NOT_CALIBRATED`` with no
number, and says why.

Three states, never collapsed
-----------------------------
1. **Never measured.** No ``calibration.json`` beside the checkpoint.
2. **Measured, did not pass.** The ECE after temperature scaling is above the bar.
   The scores still *rank* pixels correctly -- temperature scaling is monotonic --
   but they are not probabilities, so no value is reported. This is the state
   ``hand-only-v2`` is in today: ECE 0.0583 against a 0.05 bar.
3. **Measured and passed.** The value is the mean temperature-scaled probability
   over the pixels called water, and ``calibration_ref`` cites the report.

State 2 is the one that matters. Before this module the service hardcoded
``NOT_CALIBRATED`` with the caveat "model output is uncalibrated; see P3-11".
That was true when written. P3-11 then ran, measured the model, and found it
short of the bar -- and the caveat went on telling every caller that the
calibration did not exist. A statement that goes stale is still false.

Why the mask never changes
--------------------------
The water threshold is 0.5. In logit space that is 0, and temperature scaling
divides the logit by T, which leaves 0 at 0. So a pixel is called water with or
without calibration; only the confidence *value* moves. That is asserted in
test_confidence.py rather than assumed, because if it were ever false,
calibrating the model would silently change the reported area.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import numpy.typing as npt

from ml.evaluation.calibration import apply_temperature
from packages.contracts import Confidence, ConfidenceBasis

#: Probabilities are clipped before the logit so 0 and 1 map to finite values.
#: 1e-6 is far below anything the sigmoid output reaches in float32 for a real
#: pixel, so it bounds the arithmetic without moving any number that matters.
_EPS = 1e-6


def _logit(probability: npt.NDArray[np.floating]) -> npt.NDArray[np.float64]:
    p = np.clip(probability.astype(np.float64), _EPS, 1.0 - _EPS)
    logits: npt.NDArray[np.float64] = np.log(p / (1.0 - p))
    return logits


def confidence_for(
    card: object,
    probability: npt.NDArray[np.floating],
    mask: npt.NDArray[np.bool_],
) -> Confidence:
    """The confidence this model is entitled to report for this mask.

    ``card`` is a :class:`~services.inference.registry.ModelCard`; typed loosely to
    keep this module free of the registry import, since the registry imports torch
    lazily and this must not.
    """
    name = getattr(card, "name", "the model")
    ece = getattr(card, "calibration_ece", None)
    passes = getattr(card, "calibration_passes", None)
    report = getattr(card, "calibration_report", None) or "the calibration report"
    bar = getattr(card, "calibration_bar", None)
    temperature = getattr(card, "calibration_temperature", None)

    # ── 1. never measured ────────────────────────────────────────────────────
    if ece is None or passes is None:
        return Confidence.not_calibrated(
            caveats=(
                f"calibration of {name} has not been measured, so its scores are "
                "not reported as probabilities",
            )
        )

    bar_text = f"{bar:g}" if bar is not None else "the required"

    # ── 2. measured, did not pass ────────────────────────────────────────────
    if not passes:
        return Confidence.not_calibrated(
            caveats=(
                f"calibration measured and did not pass: ECE {ece:.4f} against a "
                f"{bar_text} bar after temperature scaling ({report})",
                "scores rank pixels reliably but are not probabilities, so no "
                "confidence value is reported",
            )
        )

    # ── 3. measured and passed ───────────────────────────────────────────────
    if temperature is None or not np.isfinite(temperature) or temperature <= 0:
        # Passing without a usable temperature means the sidecar is incomplete.
        # Reporting the raw score would be reporting the uncalibrated number the
        # calibration exists to correct.
        return Confidence.not_calibrated(
            caveats=(
                f"calibration of {name} passed but recorded no usable temperature, "
                "so a calibrated probability cannot be computed",
            )
        )

    called = probability[mask]
    if called.size == 0:
        return Confidence.not_calibrated(
            caveats=(
                "no pixels were called water, so there is nothing to report " "a confidence for",
            )
        )

    calibrated = apply_temperature(_logit(called), float(temperature))
    value = Decimal(str(round(float(np.mean(calibrated)), 4)))

    return Confidence(
        basis=ConfidenceBasis.CALIBRATED_PROBABILITY,
        value=value,
        interval=None,
        calibration_ref=report,
        agreement_iou=None,
        caveats=(
            f"mean temperature-scaled water probability over the {called.size} "
            f"pixels called water (T={temperature:.3f})",
            f"calibration ECE {ece:.4f}, under a {bar_text} bar",
        ),
    )
