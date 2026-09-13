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


import numpy as np
import pytest

from ml.evaluation.segmentation import confusion

pytestmark = pytest.mark.unit


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


def test_f1_is_zero_for_a_complete_miss() -> None:
    """The case the first F1 fix still got wrong.

    Water is present and the model predicts nothing: TP=0, FP=0, FN>0. Precision
    is 0/0 and therefore undefined, so guarding on "precision or recall is
    undefined" returned NaN -- hiding the model's *worst* chips from any
    ``nanmean``, which is the same inflation the first fix was meant to remove,
    reached by a different branch.

    F1 = 2TP/(2TP+FP+FN) is 0 here, and IoU already said 0. Computing F1 from the
    counts rather than from precision and recall removes the branch entirely, so
    the two metrics can no longer disagree.
    """
    predicted = np.array([[0, 0, 0]], dtype=np.int16)
    truth = np.array([[0, 1, 1]], dtype=np.int16)
    metrics = confusion(predicted, truth, ignore_value=-1)

    assert metrics.true_positive == 0
    assert np.isnan(metrics.precision)  # genuinely undefined: nothing was claimed
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert metrics.intersection_over_union == 0.0


def test_f1_and_iou_agree_on_every_degenerate_case() -> None:
    """Both are zero exactly when TP is zero and something was present or claimed.

    Asserted as a property rather than case by case, because two review rounds
    found F1 disagreeing with IoU in two different corners.
    """
    cases = [
        (np.array([[0, 0]]), np.array([[1, 1]])),  # complete miss
        (np.array([[1, 1]]), np.array([[0, 0]])),  # all false positives
        (np.array([[1, 0]]), np.array([[0, 1]])),  # entirely wrong
    ]
    for predicted, truth in cases:
        m = confusion(predicted.astype(np.int16), truth.astype(np.int16), ignore_value=-1)
        assert m.f1 == 0.0
        assert m.intersection_over_union == 0.0

    empty = confusion(
        np.array([[0, 0]], dtype=np.int16), np.array([[0, 0]], dtype=np.int16), ignore_value=-1
    )
    assert np.isnan(empty.f1)
    assert np.isnan(empty.intersection_over_union) or empty.intersection_over_union == 0.0


def test_f1_of_a_perfect_prediction_is_one() -> None:
    m = confusion(
        np.array([[1, 1, 0]], dtype=np.int16),
        np.array([[1, 1, 0]], dtype=np.int16),
        ignore_value=-1,
    )
    assert m.f1 == 1.0
