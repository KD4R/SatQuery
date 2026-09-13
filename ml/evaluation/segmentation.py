"""Segmentation metrics with explicit no-data handling.

The trap this module exists to close
------------------------------------
Sen1Floods11 labels use ``-1`` for No Data / Invalid, ``0`` for Not Water and ``1``
for Water (per the dataset's own documentation). Chip borders carry substantial
``-1``.

If those pixels are counted as background, every metric is inflated -- a model that
predicts "not water" everywhere scores well on the no-data margin, and that margin
is a meaningful fraction of a 512x512 chip. The inflation is largest for exactly
the metrics one wants to quote.

So the ignore value is a **required** argument with no default that silently
disappears, and the returned object records how many pixels were excluded, so a
report can state it.

Reference: Sen1Floods11 official repository,
https://github.com/cloudtostreet/Sen1Floods11
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

#: Sen1Floods11's no-data label. Named rather than inlined so that a different
#: dataset with a different convention has an obvious place to declare it.
SEN1FLOODS11_IGNORE_VALUE = -1


@dataclass(frozen=True)
class SegmentationMetrics:
    """Confusion counts and the ratios derived from them.

    All ratios are computed from the same four counts, so they cannot disagree with
    each other. ``ignored_pixels`` is carried so that any report generated from this
    object can state how much of the chip was excluded -- a metric quoted without
    that number is not reproducible.
    """

    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    ignored_pixels: int

    @property
    def valid_pixels(self) -> int:
        """Pixels that took part in the comparison."""
        return self.true_positive + self.false_positive + self.false_negative + self.true_negative

    @property
    def intersection_over_union(self) -> float:
        """IoU for the positive class. ``nan`` when the class is absent from both."""
        denominator = self.true_positive + self.false_positive + self.false_negative
        if denominator == 0:
            # Neither predicted nor present. Returning 1.0 here would reward a model
            # for correctly finding nothing in a chip with nothing to find, which
            # makes aggregate scores meaningless; nan excludes it from the mean.
            return float("nan")
        return self.true_positive / denominator

    @property
    def accuracy(self) -> float:
        """Fraction of scorable pixels classified correctly.

        Provided so that reports can *show* how misleading it is, not so anyone
        quotes it. On this benchmark water is roughly a tenth of the pixels, so
        predicting no water anywhere scores about 0.89 here while scoring 0.0 IoU.
        Any target expressed as "N% accuracy" is a target a broken model meets.
        """
        if self.valid_pixels == 0:
            return float("nan")
        return (self.true_positive + self.true_negative) / self.valid_pixels

    @property
    def prevalence(self) -> float:
        """Fraction of scorable pixels that are actually water.

        The number that makes ``accuracy`` interpretable: 1 - prevalence is what a
        model predicting nothing would score.
        """
        if self.valid_pixels == 0:
            return float("nan")
        return (self.true_positive + self.false_negative) / self.valid_pixels

    @property
    def precision(self) -> float:
        """Of the pixels called water, the fraction that were water."""
        denominator = self.true_positive + self.false_positive
        if denominator == 0:
            return float("nan")
        return self.true_positive / denominator

    @property
    def recall(self) -> float:
        """Of the water pixels present, the fraction that were found."""
        denominator = self.true_positive + self.false_negative
        if denominator == 0:
            return float("nan")
        return self.true_positive / denominator

    @property
    def f1(self) -> float:
        """Harmonic mean of precision and recall."""
        # Computed from the counts rather than from precision and recall.
        #
        # The harmonic-mean form has to special-case every way its inputs can be
        # undefined, and two successive review rounds found a case it still got
        # wrong: a complete miss (water present, nothing predicted) leaves
        # precision NaN and recall 0, and returning NaN there hides the model's
        # worst chips from any ``nanmean``. The identity
        #
        #     F1 = 2TP / (2TP + FP + FN)
        #
        # has no such branches. It is 0 whenever there were positives to find or
        # positives claimed and none of them were right, and it is undefined only
        # when all three counts are zero -- no water in the truth and none
        # predicted, where there is genuinely nothing to score.
        #
        # This also makes agreement with ``intersection_over_union`` structural
        # rather than coincidental: both are now zero exactly when TP is zero and
        # something was either present or claimed.
        denominator = 2 * self.true_positive + self.false_positive + self.false_negative
        if denominator == 0:
            return float("nan")
        return 2.0 * self.true_positive / denominator


def confusion(
    predicted: npt.NDArray[np.bool_] | npt.NDArray[np.integer],
    truth: npt.NDArray[np.integer],
    *,
    ignore_value: int,
) -> SegmentationMetrics:
    """Compare a predicted mask against labels, excluding no-data pixels.

    Parameters
    ----------
    predicted
        Boolean or 0/1 array. Must be the same shape as ``truth``.
    truth
        Label array using ``1`` for the positive class, ``0`` for the negative
        class and ``ignore_value`` for pixels that must not be scored.
    ignore_value
        The no-data label. Required, deliberately: there is no safe default,
        because guessing wrong inflates every metric silently. For Sen1Floods11
        pass :data:`SEN1FLOODS11_IGNORE_VALUE`.

    Returns
    -------
    SegmentationMetrics
    """
    if predicted.shape != truth.shape:
        raise ValueError(
            f"predicted and truth must have identical shape, got "
            f"{predicted.shape} and {truth.shape}"
        )

    valid = truth != ignore_value
    ignored = int(np.count_nonzero(~valid))

    # Reduce to the valid subset once, then count. Doing the masking up front means
    # no individual count can accidentally forget it.
    truth_remaining = np.asarray(truth)[valid]

    # Verify the label encoding before comparing anything.
    #
    # This guard exists because of a specific, nasty failure mode: casting a label
    # array to bool turns -1 into True. If the caller passes the wrong
    # ``ignore_value``, every no-data pixel silently becomes a *positive* label and
    # the metrics describe a completely different problem -- without raising.
    #
    # So rather than casting, the positive class is tested explicitly as ``== 1``
    # and anything that is neither 0 nor 1 nor the ignore value is rejected.
    unexpected = np.setdiff1d(np.unique(truth_remaining), np.array([0, 1]))
    if unexpected.size > 0:
        raise ValueError(
            f"truth contains labels {unexpected.tolist()} that are neither 0, 1, nor "
            f"the declared ignore_value {ignore_value}. Either the ignore_value is "
            "wrong for this dataset or the label encoding is not what was assumed; "
            "both would silently corrupt every metric below."
        )

    # The identical guard on the prediction side. The first version of this
    # function checked only ``truth``, on the reasoning that predictions come from
    # our own code and are therefore trustworthy -- which is wrong twice over: a
    # model emitting class IDs (0/1/2 for land/water/cloud) and an argmax over the
    # wrong axis both produce integer arrays that cast to ``True`` for every
    # non-zero entry, scoring class 2 as water and inflating recall. A boolean
    # array is passed through as-is; anything integral must be strictly 0/1.
    pred_remaining = np.asarray(predicted)[valid]
    if pred_remaining.dtype != np.bool_:
        unexpected_pred = np.setdiff1d(np.unique(pred_remaining), np.array([0, 1]))
        if unexpected_pred.size > 0:
            raise ValueError(
                f"predicted contains values {unexpected_pred.tolist()} that are "
                "neither 0 nor 1. Casting those to bool would score every non-zero "
                "value as the positive class. Threshold or one-hot the model output "
                "explicitly before scoring it."
            )
    pred_valid = pred_remaining.astype(bool)
    truth_valid = truth_remaining == 1

    return SegmentationMetrics(
        true_positive=int(np.count_nonzero(pred_valid & truth_valid)),
        false_positive=int(np.count_nonzero(pred_valid & ~truth_valid)),
        false_negative=int(np.count_nonzero(~pred_valid & truth_valid)),
        true_negative=int(np.count_nonzero(~pred_valid & ~truth_valid)),
        ignored_pixels=ignored,
    )


def mask_agreement_iou(
    mask_a: npt.NDArray[np.bool_],
    mask_b: npt.NDArray[np.bool_],
) -> float:
    """IoU between two predicted masks, with no ground truth involved.

    This is the number behind
    :attr:`~packages.contracts.ConfidenceBasis.MODEL_AGREEMENT`:
    the deterministic Otsu baseline and the learned model are run on the same input
    and their outputs compared. Because the two methods are independent, their
    agreement is a genuine uncertainty signal rather than a model's opinion of
    itself.

    Returns ``nan`` when both masks are empty -- unanimous agreement that there is
    nothing there is not evidence about the model's reliability, so it must not be
    averaged in as a perfect score.
    """
    if mask_a.shape != mask_b.shape:
        raise ValueError(f"masks must have identical shape, got {mask_a.shape} and {mask_b.shape}")
    a = np.asarray(mask_a, dtype=bool)
    b = np.asarray(mask_b, dtype=bool)
    union = int(np.count_nonzero(a | b))
    if union == 0:
        return float("nan")
    return int(np.count_nonzero(a & b)) / union


def pool(metrics: Iterable[SegmentationMetrics]) -> SegmentationMetrics:
    """Sum confusion counts across chips into one dataset-level result.

    Pooled, not averaged, and the difference is not cosmetic. Averaging per-chip
    IoU weights a 512x512 chip holding nine water pixels exactly as heavily as one
    that is half flooded, and on this benchmark most chips are nearly dry -- so the
    mean is dominated by chips where the denominator is a handful of pixels and one
    misplaced pixel swings the score. Pooling weights each chip by how much water
    was actually there to find, which is the aggregation the Sen1Floods11 literature
    reports and the only one comparable to a published figure.

    Both belong in a report. The mean says how the model does on a typical chip;
    the pooled figure says how it does on the region. They differ by roughly a
    factor of two here, and quoting either alone without saying which is how two
    people end up arguing about the same model.

    An empty input is an error rather than a zeroed result: a pooled score over no
    chips is not zero, it is undefined, and returning 0.0 would put a real-looking
    number in a report.
    """
    collected = list(metrics)
    if not collected:
        raise ValueError("cannot pool an empty sequence of metrics")
    return SegmentationMetrics(
        true_positive=sum(m.true_positive for m in collected),
        false_positive=sum(m.false_positive for m in collected),
        false_negative=sum(m.false_negative for m in collected),
        true_negative=sum(m.true_negative for m in collected),
        ignored_pixels=sum(m.ignored_pixels for m in collected),
    )
