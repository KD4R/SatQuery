"""Turning a model's scores into probabilities, and measuring whether they are.

WHAT "CALIBRATED" MEANS HERE, AND WHY THE DISTINCTION IS NOT PEDANTIC
---------------------------------------------------------------------
A sigmoid output is a number in [0, 1]. That is the only thing it has in common
with a probability. A model can rank pixels perfectly -- separating water from land
better than any other -- while every score it emits is wrong as a probability: if
the pixels it scores 0.9 turn out to be water 60% of the time, then "0.9" means
0.6, and a caller who thresholds at 0.8 to get "high confidence" detections gets
something else entirely.

Accuracy metrics cannot see this. IoU and F1 depend only on which side of the
threshold each pixel falls, so a model whose scores are systematically overconfident
scores exactly as well as one whose scores are honest. That is why ADR-0007 D5
requires a confidence to declare its basis, and why every result so far has shipped
as NOT_CALIBRATED: not because the model is bad, but because nobody had measured
whether its numbers mean what they look like.

TEMPERATURE SCALING
-------------------
One parameter. Divide the logits by T before the sigmoid, and fit T to minimise
negative log-likelihood on held-out data. T > 1 softens an overconfident model;
T < 1 sharpens an underconfident one.

It is deliberately the weakest useful method. A single monotonic parameter cannot
change the ordering of any two pixels, so IoU, F1 and every threshold-based number
in reports/evaluation.md are provably unchanged by it -- which means calibration
can be added without any accuracy figure moving, and no reader has to wonder
whether the model got better or the metric got friendlier. Anything richer (Platt
scaling per region, isotonic regression) buys a little ECE at the cost of that
guarantee.

MEASURED ON DATA IT WAS NOT FITTED ON
-------------------------------------
Fitting T and reporting ECE on the same pixels reports how well one parameter can
fit 24 million numbers, which is: perfectly. The fit and the report must be
disjoint, and the caller is required to make them so -- see ml/scripts/calibrate.py,
which fits on one held-out region and reports on the other.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

#: Bins for the reliability diagram. Ten equal-width bins on [0, 1] is the
#: convention in the calibration literature; stated here because ECE is not
#: comparable across different binning schemes and a number quoted without its
#: bin count is not reproducible.
DEFAULT_BINS = 10


@dataclass(frozen=True)
class ReliabilityBin:
    """One row of a reliability diagram."""

    lower: float
    upper: float
    count: int
    mean_confidence: float
    observed_frequency: float

    @property
    def gap(self) -> float:
        """How far the bin's claim is from what happened. Signed: positive is
        overconfident."""
        return self.mean_confidence - self.observed_frequency


@dataclass(frozen=True)
class Calibration:
    """A reliability diagram and the scalars derived from it."""

    bins: tuple[ReliabilityBin, ...]
    #: Expected calibration error: the count-weighted mean absolute gap. The
    #: headline number, and the one that is meaningless without the bin count.
    ece: float
    #: The largest gap in any populated bin. Reported alongside ECE because a model
    #: can have a small ECE and still be badly wrong in the region a caller
    #: actually thresholds in -- the bins near 1.0 hold few pixels and are averaged
    #: away.
    max_gap: float
    #: Fraction of the samples that are positive. ECE has to be read against it:
    #: a model that outputs the prevalence everywhere is perfectly calibrated and
    #: useless.
    prevalence: float


def reliability(
    probabilities: npt.NDArray[np.floating],
    labels: npt.NDArray[np.integer] | npt.NDArray[np.bool_],
    *,
    bins: int = DEFAULT_BINS,
) -> Calibration:
    """Bin predictions by confidence and compare each bin's claim to reality.

    ``probabilities`` and ``labels`` must be flat and the same length, already
    restricted to scorable pixels -- this function has no notion of a no-data
    value, and silently including them would put a large block of "label 0" into
    every bin.
    """
    probabilities = np.asarray(probabilities, dtype=np.float64).ravel()
    labels = np.asarray(labels).ravel()

    if probabilities.shape != labels.shape:
        raise ValueError(
            f"{probabilities.size} probabilities against {labels.size} labels; "
            "they must be the same flat length"
        )
    if probabilities.size == 0:
        raise ValueError("cannot measure calibration on zero samples")
    if bins < 1:
        raise ValueError(f"bins must be positive, got {bins}")
    if not np.all(np.isfinite(probabilities)):
        raise ValueError("probabilities contain non-finite values")
    if probabilities.min() < 0.0 or probabilities.max() > 1.0:
        raise ValueError(
            f"probabilities lie in [{probabilities.min()}, {probabilities.max()}], "
            "outside [0, 1] -- these look like logits rather than probabilities"
        )

    truth = labels.astype(bool)
    edges = np.linspace(0.0, 1.0, bins + 1)
    # Right-closed except for the first bin, so 0.0 and 1.0 both land somewhere.
    index = np.clip(np.searchsorted(edges, probabilities, side="left") - 1, 0, bins - 1)

    rows: list[ReliabilityBin] = []
    weighted_gap = 0.0
    max_gap = 0.0
    for b in range(bins):
        selected = index == b
        count = int(selected.sum())
        if count == 0:
            # Kept in the table with nan, not dropped: an empty bin is information
            # (the model never expresses that confidence), and renumbering the rows
            # would make two runs' diagrams incomparable.
            rows.append(
                ReliabilityBin(
                    lower=float(edges[b]),
                    upper=float(edges[b + 1]),
                    count=0,
                    mean_confidence=float("nan"),
                    observed_frequency=float("nan"),
                )
            )
            continue
        confidence = float(probabilities[selected].mean())
        observed = float(truth[selected].mean())
        rows.append(
            ReliabilityBin(
                lower=float(edges[b]),
                upper=float(edges[b + 1]),
                count=count,
                mean_confidence=confidence,
                observed_frequency=observed,
            )
        )
        gap = abs(confidence - observed)
        weighted_gap += gap * count
        max_gap = max(max_gap, gap)

    return Calibration(
        bins=tuple(rows),
        ece=weighted_gap / probabilities.size,
        max_gap=max_gap,
        prevalence=float(truth.mean()),
    )


def apply_temperature(
    logits: npt.NDArray[np.floating], temperature: float
) -> npt.NDArray[np.float64]:
    """Sigmoid of the logits divided by ``temperature``."""
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError(f"temperature must be finite and positive, got {temperature}")
    scaled = np.asarray(logits, dtype=np.float64) / temperature

    # Masked rather than np.where, which evaluates BOTH branches and so overflows
    # on exactly the inputs the two-branch form exists to protect: np.exp(+5000)
    # is computed, warns, becomes inf, and inf/inf is nan. The nan then travels
    # into ECE as a number rather than an error. Each branch here only ever
    # exponentiates a non-positive value, so neither can overflow.
    result = np.empty_like(scaled)
    positive = scaled >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-scaled[positive]))
    negative_exp = np.exp(scaled[~positive])
    result[~positive] = negative_exp / (1.0 + negative_exp)
    return result


def negative_log_likelihood(
    logits: npt.NDArray[np.floating],
    labels: npt.NDArray[np.integer] | npt.NDArray[np.bool_],
    temperature: float,
) -> float:
    """Mean NLL of the labels under the temperature-scaled logits.

    The objective temperature scaling minimises. Not ECE: ECE is a binned,
    piecewise-constant statistic with zero gradient almost everywhere and a
    dependence on the bin count, so optimising it directly fits the binning.
    """
    scaled = np.asarray(logits, dtype=np.float64) / temperature
    truth = np.asarray(labels).ravel().astype(np.float64)
    # log(1 + exp(x)) computed stably, then the standard logistic-loss identity.
    softplus = np.logaddexp(0.0, -np.abs(scaled))
    loss = softplus + np.maximum(scaled, 0.0) - scaled * truth
    return float(loss.mean())


def fit_temperature(
    logits: npt.NDArray[np.floating],
    labels: npt.NDArray[np.integer] | npt.NDArray[np.bool_],
    *,
    bounds: tuple[float, float] = (0.05, 20.0),
    tolerance: float = 1e-4,
) -> float:
    """The temperature minimising NLL, by golden-section search.

    Golden-section rather than gradient descent because the objective is strictly
    unimodal in T for a fixed set of logits, one-dimensional, and cheap -- so a
    bracketing search converges in about forty evaluations with no learning rate to
    tune and no possibility of diverging. Adding torch here would also make
    calibration require the deep-learning stack, which the rest of ``ml/evaluation``
    deliberately does not.

    The bounds are wide and clamped rather than open: a degenerate input (all
    labels one class) drives T to an endpoint, and returning 20.0 with the report
    showing the ECE it produced is more informative than an optimiser that runs
    away.
    """
    logits = np.asarray(logits, dtype=np.float64).ravel()
    labels = np.asarray(labels).ravel()
    if logits.shape != labels.shape:
        raise ValueError(f"{logits.size} logits against {labels.size} labels")
    if logits.size == 0:
        raise ValueError("cannot fit a temperature on zero samples")

    low, high = bounds
    if not 0 < low < high:
        raise ValueError(f"bounds must satisfy 0 < low < high, got {bounds}")

    golden = (np.sqrt(5.0) - 1.0) / 2.0
    a, b = low, high
    c = b - golden * (b - a)
    d = a + golden * (b - a)
    fc = negative_log_likelihood(logits, labels, c)
    fd = negative_log_likelihood(logits, labels, d)

    while b - a > tolerance:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - golden * (b - a)
            fc = negative_log_likelihood(logits, labels, c)
        else:
            a, c, fc = c, d, fd
            d = a + golden * (b - a)
            fd = negative_log_likelihood(logits, labels, d)

    return float((a + b) / 2.0)
