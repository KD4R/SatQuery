"""A small U-Net for SAR water segmentation.

Why a U-Net, and why a small one
---------------------------------
PANGAEA (arXiv:2412.04204) found that geospatial foundation models do not
consistently outperform supervised models including U-Net under limited labelled
data, across resolutions, sensors and regions. Prithvi-EO is additionally an
*optical* model, which is a sensor mismatch for a chain running on Sentinel-1
precisely because monsoon flooding sits under cloud. Foundation models belong in
the ablation table as a comparison row, not in the analysis path.

Small because the training set is sixty chips. A wide network on sixty chips
memorises them; the validation score then measures recall of the training set. The
default here is roughly 0.5 M parameters — enough capacity for a two-class
texture-and-tone problem, little enough that region-held-out validation means
something.

What it has to learn that Otsu cannot
--------------------------------------
Not a sharper boundary. ADR-0007 D13 measured the deterministic baseline at IoU
0.704 where a chip is more than 30% water — the boundary is already close to
adequate. It measured 0.004 where a chip is less than 1% water, because Otsu
always splits a histogram and therefore invents a flood on dry ground.

So the capability being added is the ability to output *nothing*. That is a
property of the training data (dry chips are kept — see ml/training/dataset.py)
and of the loss (which must not be dominated by the water class), more than of the
architecture.
"""

from __future__ import annotations

import torch
from torch import Tensor, nn


class ConvBlock(nn.Module):
    """Two 3x3 convolutions, each followed by normalisation and a nonlinearity.

    GroupNorm rather than BatchNorm. Batch statistics are unusable here: the
    batch is 4 crops on a 3 GB machine, and a batch that happens to contain only
    dry crops has a completely different mean from one containing a flood, so
    BatchNorm would make each sample's normalisation depend on which other samples
    it was randomly grouped with. GroupNorm is batch-independent and behaves
    identically at training and inference, which also removes a class of
    train/serve skew.
    """

    def __init__(self, in_channels: int, out_channels: int, groups: int = 8) -> None:
        super().__init__()
        groups = min(groups, out_channels)
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.GroupNorm(groups, out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: Tensor) -> Tensor:
        out: Tensor = self.block(x)
        return out


class UNet(nn.Module):
    """Encoder-decoder with skip connections, emitting one logit per pixel.

    Emits **logits**, not probabilities. Two reasons, and the second is the
    important one:

    * ``BCEWithLogitsLoss`` is numerically stable in a way that sigmoid followed
      by BCE is not.
    * A sigmoid output invites being read as a probability, and it is not one — it
      is a normalised score from an uncalibrated model. ADR-0007 D5 requires a
      confidence to declare its basis, and ``CALIBRATED_PROBABILITY`` requires a
      calibration report that does not yet exist. Keeping the head as logits makes
      the missing step visible rather than papering over it with a number that
      looks like a probability.
    """

    def __init__(
        self,
        in_channels: int = 2,
        base_channels: int = 8,
        depth: int = 4,
    ) -> None:
        super().__init__()
        if depth < 1:
            raise ValueError(f"depth must be at least 1, got {depth}")

        self.in_channels = in_channels
        self.depth = depth
        widths = [base_channels * (2**i) for i in range(depth)]

        self.encoders = nn.ModuleList()
        channels = in_channels
        for width in widths:
            self.encoders.append(ConvBlock(channels, width))
            channels = width

        self.pool = nn.MaxPool2d(2)
        self.bottleneck = ConvBlock(channels, channels * 2)
        channels *= 2

        self.upsamples = nn.ModuleList()
        self.decoders = nn.ModuleList()
        for width in reversed(widths):
            self.upsamples.append(nn.ConvTranspose2d(channels, width, kernel_size=2, stride=2))
            # width * 2: the upsampled features concatenated with the skip.
            self.decoders.append(ConvBlock(width * 2, width))
            channels = width

        self.head = nn.Conv2d(channels, 1, kernel_size=1)

    def forward(self, x: Tensor) -> Tensor:
        if x.shape[-1] % 2 ** self.depth or x.shape[-2] % 2**self.depth:
            raise ValueError(
                f"input {tuple(x.shape[-2:])} must be divisible by "
                f"{2 ** self.depth} for depth {self.depth}; otherwise the decoder "
                "silently misaligns with its skip connections after pooling"
            )

        skips: list[Tensor] = []
        for encoder in self.encoders:
            x = encoder(x)
            skips.append(x)
            x = self.pool(x)

        x = self.bottleneck(x)

        for upsample, decoder, skip in zip(self.upsamples, self.decoders, reversed(skips)):
            x = upsample(x)
            x = torch.cat([x, skip], dim=1)
            x = decoder(x)

        logits: Tensor = self.head(x)
        return logits.squeeze(1)

    @property
    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())


def masked_bce_dice_loss(
    logits: Tensor,
    target: Tensor,
    weight: Tensor,
    *,
    dice_weight: float = 0.5,
    epsilon: float = 1.0,
) -> Tensor:
    """Binary cross-entropy plus soft Dice, both masked by pixel validity.

    **Masked** — ``weight`` is 0 on no-data pixels. Sen1Floods11 marks chip borders
    ``-1``; training those as land teaches the model that the edge of every image
    is dry, and on a chip that is 90% no-data it would be almost the only thing
    learned.

    **Both terms, not one.** Cross-entropy alone is dominated by the majority
    class, and water is a small minority on most chips — a model that predicts
    "dry everywhere" scores well on BCE and is useless. Dice is computed on the
    overlap and is largely insensitive to how much background there is, so it
    keeps pressure on the positive class. But Dice alone is unstable when a crop
    contains no water at all: the numerator is zero whatever the model does, so it
    gives almost no gradient on exactly the dry crops D13 says matter most. Each
    term covers the other's blind spot.

    **The epsilon is 1.0, not 1e-6.** On a crop with no water and no prediction,
    Dice becomes ``eps / eps`` = 1, a perfect score, correctly saying there was
    nothing to find. A tiny epsilon would make that ratio numerically wild and
    inject noise from the emptiest crops.
    """
    if not (logits.shape == target.shape == weight.shape):
        raise ValueError(
            f"shape mismatch: logits {tuple(logits.shape)}, target "
            f"{tuple(target.shape)}, weight {tuple(weight.shape)}"
        )

    valid = weight.sum().clamp(min=1.0)

    bce = nn.functional.binary_cross_entropy_with_logits(logits, target, reduction="none")
    bce = (bce * weight).sum() / valid

    probabilities = torch.sigmoid(logits) * weight
    truth = target * weight
    intersection = (probabilities * truth).sum()
    denominator = probabilities.sum() + truth.sum()
    dice = 1.0 - (2.0 * intersection + epsilon) / (denominator + epsilon)

    total: Tensor = (1.0 - dice_weight) * bce + dice_weight * dice
    return total
