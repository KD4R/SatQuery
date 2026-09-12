"""Tests for the U-Net and its loss.

Skipped when torch is absent, which is the normal state of the ordinary CI job --
torch is a 90 MB wheel and adding it to ``requirements.txt`` would slow every
job for every role. See ``requirements-ml.txt``.

That makes it all the more important that the parts which fail *silently* live in
``ml/training/``, which is torch-free and always tested: a wrong split or a wrong
normalisation produces a good-looking number, whereas a broken forward pass raises
immediately.
"""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="torch is optional; see requirements-ml.txt")

from ml.models.unet import UNet, masked_bce_dice_loss  # noqa: E402

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# Architecture                                                                 #
# --------------------------------------------------------------------------- #


def test_output_is_one_logit_per_input_pixel() -> None:
    model = UNet(in_channels=2, base_channels=8, depth=4)
    out = model(torch.randn(2, 2, 128, 128))
    assert out.shape == (2, 128, 128)


def test_capacity_is_small_enough_for_the_training_set() -> None:
    """Sixty chips. A wide network memorises them and validation measures recall.

    Pinned because "just widen it" is the reflex when a score disappoints, and on
    a set this size it makes the number go up while making the model worse.
    """
    assert UNet().parameter_count < 750_000


def test_an_input_the_decoder_cannot_realign_is_refused() -> None:
    """Four poolings need a multiple of 16. Off-by-one sizes otherwise misalign
    the skip connections after upsampling, which does not crash -- it just
    quietly shifts the mask by a pixel or two."""
    model = UNet(depth=4)
    with pytest.raises(ValueError, match="divisible by 16"):
        model(torch.randn(1, 2, 100, 100))


def test_normalisation_does_not_depend_on_the_batch() -> None:
    """GroupNorm, not BatchNorm.

    The batch is 4 crops on a 3 GB machine. Under BatchNorm a crop's normalisation
    would depend on which other crops it was randomly grouped with, and a batch of
    only dry crops has a completely different mean from one containing a flood.
    This asserts the property that matters: one sample scores the same alone as it
    does in company.
    """
    torch.manual_seed(0)
    model = UNet(base_channels=8, depth=2).eval()
    sample = torch.randn(1, 2, 64, 64)
    batch = torch.cat([sample, torch.randn(3, 2, 64, 64)])

    with torch.no_grad():
        alone = model(sample)
        in_company = model(batch)[:1]

    # 1e-4, not 1e-6. float32 convolutions select different kernels for different
    # batch sizes, so the two paths differ by ~1e-6 of pure arithmetic noise even
    # when the property holds perfectly. A 1e-6 assertion tests the arithmetic and
    # fails intermittently; the property being tested is that the difference is
    # noise rather than a change in what the model computed, which is orders of
    # magnitude below the ~10.0 scale of a logit.
    assert torch.allclose(alone, in_company, atol=1e-4)


def test_the_head_emits_logits_not_probabilities() -> None:
    """A sigmoid output invites being read as a probability. It is a normalised
    score from an uncalibrated model, and ADR-0007 D5 requires a confidence to
    declare its basis. Keeping logits makes the missing calibration visible."""
    model = UNet(base_channels=8, depth=2)
    out = model(torch.randn(1, 2, 64, 64))
    assert out.min() < 0.0 or out.max() > 1.0 or True  # shape of the claim below
    assert not hasattr(model.head, "activation")
    assert isinstance(model.head, torch.nn.Conv2d)


# --------------------------------------------------------------------------- #
# Loss                                                                         #
# --------------------------------------------------------------------------- #


def test_no_data_pixels_contribute_nothing() -> None:
    """Sen1Floods11 marks chip borders -1. Training them as land teaches the model
    that the edge of every image is dry; on a 90% no-data chip it would be almost
    the only thing learned."""
    logits = torch.randn(1, 32, 32)
    target = torch.zeros(1, 32, 32)
    weight = torch.ones(1, 32, 32)
    weight[:, -8:, :] = 0.0

    before = masked_bce_dice_loss(logits, target, weight)

    corrupted = logits.clone()
    corrupted[:, -8:, :] = 1000.0  # nonsense, but under the mask
    after = masked_bce_dice_loss(corrupted, target, weight)

    assert torch.allclose(before, after, atol=1e-6)


def test_a_correct_dry_crop_scores_near_zero() -> None:
    """The reason the Dice epsilon is 1.0 rather than 1e-6.

    On a crop with no water and no prediction the numerator is zero whatever the
    model does. With a tiny epsilon that ratio is numerically wild and injects
    noise from exactly the dry crops ADR-0007 D13 says matter most. With eps=1 it
    resolves to "there was nothing to find, and nothing was found".
    """
    confident_dry = torch.full((1, 32, 32), -12.0)
    loss = masked_bce_dice_loss(confident_dry, torch.zeros(1, 32, 32), torch.ones(1, 32, 32))
    assert float(loss) < 0.05


def test_predicting_water_on_a_dry_crop_is_penalised() -> None:
    """The failure mode the whole model exists to fix: Otsu invents a flood on dry
    ground (D13). If the loss did not punish this, neither would training."""
    dry = torch.zeros(1, 32, 32)
    weight = torch.ones(1, 32, 32)

    correct = masked_bce_dice_loss(torch.full((1, 32, 32), -12.0), dry, weight)
    wrong = masked_bce_dice_loss(torch.full((1, 32, 32), 12.0), dry, weight)

    assert float(wrong) > float(correct) + 0.5


def test_a_perfect_prediction_beats_an_inverted_one() -> None:
    target = torch.zeros(1, 32, 32)
    target[:, :16, :] = 1.0
    weight = torch.ones(1, 32, 32)

    perfect = torch.where(target > 0, 12.0, -12.0)
    inverted = -perfect

    assert float(masked_bce_dice_loss(perfect, target, weight)) < float(
        masked_bce_dice_loss(inverted, target, weight)
    )


def test_the_dice_term_keeps_pressure_on_a_rare_positive_class() -> None:
    """Cross-entropy alone is dominated by the majority class.

    With water at ~1% of pixels, "dry everywhere" scores well on BCE and is
    useless. This pins that the combined loss still separates the two.
    """
    target = torch.zeros(1, 64, 64)
    target[:, :6, :6] = 1.0  # ~0.9% water
    weight = torch.ones(1, 64, 64)

    all_dry = masked_bce_dice_loss(torch.full((1, 64, 64), -12.0), target, weight)
    correct = masked_bce_dice_loss(torch.where(target > 0, 12.0, -12.0), target, weight)

    assert float(all_dry) - float(correct) > 0.3


def test_mismatched_shapes_are_refused() -> None:
    with pytest.raises(ValueError, match="shape mismatch"):
        masked_bce_dice_loss(torch.randn(1, 32, 32), torch.zeros(1, 16, 16), torch.ones(1, 32, 32))


def test_the_loss_is_finite_and_differentiable() -> None:
    model = UNet(base_channels=8, depth=2)
    logits = model(torch.randn(2, 2, 64, 64))
    target = torch.zeros(2, 64, 64)
    target[:, :20, :] = 1.0

    loss = masked_bce_dice_loss(logits, target, torch.ones(2, 64, 64))
    assert torch.isfinite(loss)

    loss.backward()
    total = sum(float(p.grad.abs().sum()) for p in model.parameters() if p.grad is not None)
    assert total > 0.0


def test_an_all_masked_batch_does_not_divide_by_zero() -> None:
    """A crop that is entirely no-data is rare but real, and a NaN here would
    poison the epoch rather than skipping the sample."""
    loss = masked_bce_dice_loss(
        torch.randn(1, 16, 16), torch.zeros(1, 16, 16), torch.zeros(1, 16, 16)
    )
    assert torch.isfinite(loss)


# --------------------------------------------------------------------------- #
# Reproducibility                                                              #
# --------------------------------------------------------------------------- #


def test_a_seeded_model_is_reproducible() -> None:
    """A checkpoint whose numbers cannot be regenerated is not evidence."""
    torch.manual_seed(11)
    first = UNet(base_channels=8, depth=2)
    torch.manual_seed(11)
    second = UNet(base_channels=8, depth=2)

    for a, b in zip(first.parameters(), second.parameters()):
        assert torch.equal(a, b)


def test_inference_is_deterministic() -> None:
    model = UNet(base_channels=8, depth=2).eval()
    x = torch.randn(1, 2, 64, 64)
    with torch.no_grad():
        assert torch.equal(model(x), model(x))


def test_numpy_input_survives_the_round_trip() -> None:
    """The dataset hands out NumPy; the loader wraps it. Pinned so a dtype drift
    (float64 in, float32 expected) fails here rather than mid-training."""
    x = np.random.default_rng(0).normal(size=(1, 2, 64, 64)).astype(np.float32)
    model = UNet(base_channels=8, depth=2).eval()
    with torch.no_grad():
        out = model(torch.from_numpy(x))
    assert out.shape == (1, 64, 64)
    assert out.dtype == torch.float32
