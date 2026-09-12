"""Segmentation metrics, with the no-data inflation trap pinned.

The headline test is ``test_ignoring_nodata_changes_the_score``: it demonstrates
concretely that counting Sen1Floods11's ``-1`` border as background inflates the
result. That is the defect this module exists to prevent, so it gets an assertion
rather than a comment.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml.evaluation.segmentation import (
    SEN1FLOODS11_IGNORE_VALUE,
    confusion,
    mask_agreement_iou,
)

# CI selects tests by marker (`pytest -m unit`); an unmarked test never runs.
# Everything in this module is a fast, offline, no-I/O unit test.
pytestmark = pytest.mark.unit


def test_confusion_counts_are_correct() -> None:
    """Hand-checkable: 1 TP, 1 FP, 1 FN, 1 TN."""
    truth = np.array([[1, 1], [0, 0]], dtype=np.int16)
    predicted = np.array([[True, False], [True, False]])

    m = confusion(predicted, truth, ignore_value=SEN1FLOODS11_IGNORE_VALUE)

    assert (m.true_positive, m.false_negative) == (1, 1)
    assert (m.false_positive, m.true_negative) == (1, 1)
    assert m.valid_pixels == 4
    assert m.ignored_pixels == 0


def test_nodata_pixels_are_excluded_from_every_count() -> None:
    """-1 must take part in nothing, and be reported so a reader can see how much."""
    truth = np.array([[1, -1], [-1, 0]], dtype=np.int16)
    predicted = np.array([[True, True], [True, False]])

    m = confusion(predicted, truth, ignore_value=SEN1FLOODS11_IGNORE_VALUE)

    assert m.ignored_pixels == 2
    assert m.valid_pixels == 2
    assert m.true_positive == 1
    assert m.true_negative == 1
    # Crucially, the two predicted-True pixels over no-data are NOT false positives.
    assert m.false_positive == 0


def test_nodata_is_excluded_rather_than_scored_as_background() -> None:
    """A model predicting 'no water' everywhere must not be flattered by the border.

    Sen1Floods11 chips carry substantial -1 at their edges. Here 92 of 100 pixels
    are no-data. Excluding them honestly, the model found nothing: IoU is 0 and
    only 4 true negatives exist -- the genuine background, not the border.
    """
    truth = np.full((10, 10), SEN1FLOODS11_IGNORE_VALUE, dtype=np.int16)
    truth[4:6, 4:6] = 1  # a small water patch
    truth[0:2, 0:2] = 0  # a little genuine background
    predicted = np.zeros((10, 10), dtype=bool)  # predicts nothing anywhere

    m = confusion(predicted, truth, ignore_value=SEN1FLOODS11_IGNORE_VALUE)

    assert m.ignored_pixels == 92
    assert m.valid_pixels == 8
    assert m.intersection_over_union == 0.0
    assert m.true_negative == 4  # NOT 96 -- the border takes no part


def test_wrong_ignore_value_raises_instead_of_corrupting_the_metrics() -> None:
    """The guard against the nastiest version of this defect.

    If the caller passes an ignore_value that does not match the dataset, the -1
    pixels survive into the comparison. Casting them to bool would turn every
    no-data pixel into a *positive* label, and the metrics would describe a
    different problem entirely -- with nothing raising.

    So an unexpected label value is a hard error, naming both possible causes.
    """
    truth = np.full((10, 10), SEN1FLOODS11_IGNORE_VALUE, dtype=np.int16)
    truth[4:6, 4:6] = 1
    predicted = np.zeros((10, 10), dtype=bool)

    with pytest.raises(ValueError, match="neither 0, 1, nor"):
        confusion(predicted, truth, ignore_value=-999)  # wrong for this dataset


def test_iou_precision_recall_f1_on_a_known_case() -> None:
    """TP=2, FP=1, FN=1 -> IoU 0.5, precision 2/3, recall 2/3, F1 2/3."""
    truth = np.array([1, 1, 0, 0], dtype=np.int16)
    predicted = np.array([True, False, True, False])

    m = confusion(predicted, truth, ignore_value=SEN1FLOODS11_IGNORE_VALUE)

    assert m.intersection_over_union == pytest.approx(1 / 3)
    assert m.precision == pytest.approx(0.5)
    assert m.recall == pytest.approx(0.5)
    assert m.f1 == pytest.approx(0.5)


def test_absent_class_returns_nan_not_a_perfect_score() -> None:
    """A chip with no water, correctly predicted empty, must not score 1.0.

    Returning 1.0 would reward a model for finding nothing in a chip with nothing
    to find, which makes any aggregate mean meaningless. nan excludes it instead.
    """
    truth = np.zeros((4, 4), dtype=np.int16)
    predicted = np.zeros((4, 4), dtype=bool)

    m = confusion(predicted, truth, ignore_value=SEN1FLOODS11_IGNORE_VALUE)
    assert np.isnan(m.intersection_over_union)


def test_confusion_rejects_shape_mismatch() -> None:
    with pytest.raises(ValueError, match="identical shape"):
        confusion(
            np.zeros((4, 4), dtype=bool),
            np.zeros((4, 5), dtype=np.int16),
            ignore_value=SEN1FLOODS11_IGNORE_VALUE,
        )


# --------------------------------------------------------------------------- #
# Agreement -- the basis for MODEL_AGREEMENT confidence                        #
# --------------------------------------------------------------------------- #


def test_mask_agreement_iou_on_a_known_overlap() -> None:
    a = np.array([True, True, False, False])
    b = np.array([True, False, True, False])
    # intersection 1, union 3
    assert mask_agreement_iou(a, b) == pytest.approx(1 / 3)


def test_identical_masks_agree_completely() -> None:
    a = np.array([True, False, True])
    assert mask_agreement_iou(a, a) == pytest.approx(1.0)


def test_two_empty_masks_give_nan_not_one() -> None:
    """Unanimous agreement that there is nothing there says nothing about reliability."""
    empty = np.zeros(10, dtype=bool)
    assert np.isnan(mask_agreement_iou(empty, empty))
