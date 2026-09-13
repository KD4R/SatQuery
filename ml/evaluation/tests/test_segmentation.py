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
    SegmentationMetrics,
    confusion,
    mask_agreement_iou,
    pool,
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
    """TP=1, FP=1, FN=1 -> IoU 1/3, precision 0.5, recall 0.5, F1 0.5."""
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


# --------------------------------------------------------------------------- #
# Pooling, and why the aggregation has to be stated                            #
# --------------------------------------------------------------------------- #


def test_pooling_sums_the_counts() -> None:
    pooled = pool(
        [
            SegmentationMetrics(
                true_positive=1,
                false_positive=2,
                false_negative=3,
                true_negative=4,
                ignored_pixels=5,
            ),
            SegmentationMetrics(
                true_positive=10,
                false_positive=20,
                false_negative=30,
                true_negative=40,
                ignored_pixels=50,
            ),
        ]
    )
    assert (pooled.true_positive, pooled.false_positive) == (11, 22)
    assert (pooled.false_negative, pooled.true_negative) == (33, 44)
    assert pooled.ignored_pixels == 55


def test_pooling_nothing_is_an_error_not_a_zero() -> None:
    """A pooled score over no chips is undefined, not 0.0.

    Returning zero would put a real-looking number into a report generated from an
    empty split -- which is exactly the class of defect the report gate exists for.
    """
    with pytest.raises(ValueError, match="empty"):
        pool([])


def test_pooled_and_mean_per_chip_iou_disagree_and_pooling_is_the_honest_one() -> None:
    """The reason both aggregations have to appear in the report.

    Two chips: one nearly dry where the model scores badly on nine water pixels,
    one substantially flooded where it does well. Averaging the two per-chip IoUs
    gives the dry chip -- nine pixels of ground truth -- the same vote as the wet
    one. Pooling weights each chip by how much water was there to find.

    The gap here is deliberately large because it is large in the real data: on the
    held-out split these two numbers are 0.26 and 0.42 for the same model.
    """
    dry = SegmentationMetrics(
        true_positive=1,
        false_positive=9,
        false_negative=8,
        true_negative=262_126,
        ignored_pixels=0,
    )
    wet = SegmentationMetrics(
        true_positive=90_000,
        false_positive=10_000,
        false_negative=10_000,
        true_negative=152_144,
        ignored_pixels=0,
    )

    mean_per_chip = (dry.intersection_over_union + wet.intersection_over_union) / 2
    pooled = pool([dry, wet]).intersection_over_union

    # The dry chip scores 1/18 = 0.056 on nine pixels of truth; the wet one
    # scores 0.818 on 100,000. The mean splits the difference as though the two
    # carried equal evidence.
    assert mean_per_chip == pytest.approx(0.437, abs=1e-3)
    assert pooled == pytest.approx(0.818, abs=1e-3)
    assert pooled > mean_per_chip


def test_accuracy_is_high_for_a_model_that_finds_nothing() -> None:
    """Pinned so the report can quote it as the floor any 'N% accuracy' target clears.

    A model predicting no water at all on a chip that is 10% water scores 0.90
    accuracy and 0.0 IoU. This is the number to refuse when someone asks for
    "90+ accuracy".
    """
    found_nothing = SegmentationMetrics(
        true_positive=0,
        false_positive=0,
        false_negative=10,
        true_negative=90,
        ignored_pixels=0,
    )
    assert found_nothing.accuracy == pytest.approx(0.90)
    assert found_nothing.prevalence == pytest.approx(0.10)
    assert found_nothing.intersection_over_union == 0.0
    assert found_nothing.accuracy == pytest.approx(1.0 - found_nothing.prevalence)
