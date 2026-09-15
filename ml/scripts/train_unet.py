#!/usr/bin/env python3
"""Train the U-Net, and report what it is worth against the baseline.

    python ml/scripts/train_unet.py --epochs 40

Run it from a normal shell. Training takes minutes to tens of minutes on CPU and
does not fit inside a tool call's timeout.

WHAT THIS SCRIPT REFUSES TO DO
------------------------------
It does not report a model score on its own. Every run scores the deterministic
baseline on the *same held-out chips* and prints the two side by side, because a
learned model without an independent baseline beside it is an unfalsifiable claim
(ADR-0007 D8). If the model does not beat 0.267, that is the result and it gets
printed.

It does not evaluate on anything it trained on. The split is by region, not by
chip — see ml/training/splits.py for why chip-level splitting would inflate the
number while looking correct.

It does not write a checkpoint that cannot be reproduced. Normalisation constants,
the split, the seed and the metrics are saved beside the weights, so a
``Measurement`` produced later can name what generated it.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from packages.contracts import BackscatterScale, Polarization
from ml.evaluation.segmentation import SEN1FLOODS11_IGNORE_VALUE, confusion
from ml.io.preflight import PreflightError
from ml.models.unet import UNet, masked_bce_dice_loss
from ml.pipeline.baseline import water_mask_single_date
from ml.sar.change import ThresholdError
from ml.training.dataset import (
    Normalisation,
    Sen1Floods11Dataset,
    fit_normalisation,
    MODEL_BANDS,
    load_chip,
    load_permanent_water_prior,
    prepare,
)
from ml.training.splits import Chip, Labelling, Split, discover_chips, split_by_region

DEFAULT_ROOT = Path("data/sen1floods11")
DEFAULT_OUT = Path("artifacts/unet")


class _TorchDataset(Dataset):
    """Thin torch wrapper. The logic lives in the torch-free dataset module."""

    def __init__(self, inner: Sen1Floods11Dataset) -> None:
        self.inner = inner

    def __len__(self) -> int:
        return len(self.inner)

    def __getitem__(self, index: int):
        x, y, w = self.inner[index]
        return torch.from_numpy(x), torch.from_numpy(y), torch.from_numpy(w)


@dataclass
class EpochResult:
    epoch: int
    train_loss: float
    validation_iou: float
    validation_f1: float
    seconds: float


def _pad_to_multiple(tensor: torch.Tensor, multiple: int) -> tuple[torch.Tensor, int, int]:
    """Pad the spatial dims up so the encoder's poolings divide evenly.

    Reflection padding, not zeros: a zero in standardised space is the dataset
    mean, so a zero border would read as ordinary land and could pull predictions
    at the image edge. Reflection continues the local texture instead, which is
    the least misleading thing available.
    """
    height, width = tensor.shape[-2:]
    pad_h = (-height) % multiple
    pad_w = (-width) % multiple
    if pad_h or pad_w:
        tensor = torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect")
    return tensor, pad_h, pad_w


@torch.no_grad()
def predict_chip(
    model: UNet, chip: Chip, normalisation: Normalisation, *, threshold: float = 0.5
) -> tuple[np.ndarray, np.ndarray]:
    """Full-chip inference. Returns (predicted mask, labels)."""
    model.eval()
    bands, labels = load_chip(chip)
    # Channel count from the model, not from the flag or the filesystem: this
    # function is also called on a resumed run, where the architecture is the
    # checkpoint's rather than this invocation's.
    include_prior = model.in_channels > len(MODEL_BANDS)
    prior = load_permanent_water_prior(chip, bands.shape[1:]) if include_prior else None
    x, _, _ = prepare(bands, labels, normalisation, prior, include_prior=include_prior)

    tensor = torch.from_numpy(x).unsqueeze(0)
    tensor, pad_h, pad_w = _pad_to_multiple(tensor, 2**model.depth)
    logits = model(tensor)
    if pad_h or pad_w:
        logits = logits[..., : logits.shape[-2] - pad_h, : logits.shape[-1] - pad_w]

    probabilities = torch.sigmoid(logits).squeeze(0).numpy()
    return probabilities >= threshold, labels


def evaluate(
    model: UNet, chips: tuple[Chip, ...], normalisation: Normalisation
) -> tuple[float, float]:
    ious, f1s = [], []
    for chip in chips:
        predicted, labels = predict_chip(model, chip, normalisation)
        if not np.any(labels != SEN1FLOODS11_IGNORE_VALUE):
            continue
        metrics = confusion(predicted, labels, ignore_value=SEN1FLOODS11_IGNORE_VALUE)
        ious.append(metrics.intersection_over_union)
        f1s.append(metrics.f1)
    if not ious:
        return float("nan"), float("nan")
    return float(np.nanmean(ious)), float(np.nanmean(f1s))


def baseline_scores(chips: tuple[Chip, ...]) -> tuple[float, float, dict[str, float]]:
    """Score the deterministic baseline on the same chips, stratified by wetness.

    Stratified because ADR-0007 D13 established that a single mean over a mixed
    set says more about the sample's dry/wet balance than about the method.
    """
    from ml.io.raster import read_raster

    ious, f1s = [], []
    buckets: dict[str, list[float]] = {"<1%": [], "1-10%": [], "10-30%": [], ">30%": []}

    for chip in chips:
        raster = read_raster(
            chip.scene,
            declared_band_order=(Polarization.VV, Polarization.VH),
            declared_scale=BackscatterScale.DECIBEL,
        )
        _, labels = load_chip(chip)
        scorable = labels != SEN1FLOODS11_IGNORE_VALUE
        if not scorable.any():
            continue
        try:
            detection = water_mask_single_date(raster, polarization=Polarization.VV)
        except (PreflightError, ThresholdError):
            continue
        metrics = confusion(detection.mask, labels, ignore_value=SEN1FLOODS11_IGNORE_VALUE)
        ious.append(metrics.intersection_over_union)
        f1s.append(metrics.f1)

        water = 100.0 * np.count_nonzero(labels[scorable] == 1) / scorable.sum()
        key = "<1%" if water < 1 else "1-10%" if water < 10 else "10-30%" if water < 30 else ">30%"
        buckets[key].append(metrics.intersection_over_union)

    stratified = {k: float(np.nanmean(v)) for k, v in buckets.items() if v}
    if not ious:
        return float("nan"), float("nan"), stratified
    return float(np.nanmean(ious)), float(np.nanmean(f1s)), stratified


def model_stratified(
    model: UNet, chips: tuple[Chip, ...], normalisation: Normalisation
) -> dict[str, float]:
    buckets: dict[str, list[float]] = {"<1%": [], "1-10%": [], "10-30%": [], ">30%": []}
    for chip in chips:
        predicted, labels = predict_chip(model, chip, normalisation)
        scorable = labels != SEN1FLOODS11_IGNORE_VALUE
        if not scorable.any():
            continue
        metrics = confusion(predicted, labels, ignore_value=SEN1FLOODS11_IGNORE_VALUE)
        water = 100.0 * np.count_nonzero(labels[scorable] == 1) / scorable.sum()
        key = "<1%" if water < 1 else "1-10%" if water < 10 else "10-30%" if water < 30 else ">30%"
        buckets[key].append(metrics.intersection_over_union)
    return {k: float(np.nanmean(v)) for k, v in buckets.items() if v}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--crop", type=int, default=256)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--base-channels", type=int, default=8)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--labelling",
        default="hand",
        choices=("hand", "weak", "all"),
        help="which labellings to TRAIN on. Validation is hand-labelled whatever "
        "this says -- scoring against automatically derived labels measures the "
        "label generator, not the model. Default hand.",
    )
    parser.add_argument(
        "--init-from",
        type=Path,
        default=None,
        help="start from another checkpoint's weights. Distinct from --resume, "
        "which continues one run: this begins a new one from a pretrained "
        "initialisation, which is how the two-stage recipe works -- pretrain on "
        "--labelling all, then fine-tune on hand labels from that checkpoint.",
    )
    parser.add_argument(
        "--prior",
        action="store_true",
        help="feed the JRC permanent-water layer as a third input channel. "
        "Postprocessing already subtracts permanent water, but only after the "
        "model has decided; as an input the model is told, and spends its "
        "capacity on boundary cases instead of relearning that certain dark "
        "regions are never floods. Trained with the channel blanked a quarter "
        "of the time so inference without JRC still works.",
    )
    parser.add_argument(
        "--val-every",
        type=int,
        default=1,
        help="run validation every N epochs (default 1). Validation is full-chip "
        "inference over every held-out chip, so at 92 chips it costs more than the "
        "training epoch it follows. The final epoch is always validated regardless, "
        "so the reported number is never stale.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="continue from artifacts/<out>/last.pt instead of starting over. "
        "Training on CPU takes minutes and a run that dies at epoch 50 should not "
        "restart at 1; this also lets a long run be split across shorter sessions.",
    )
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    try:
        chips = discover_chips(args.root)
        split = split_by_region(chips)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    if args.labelling != "all":
        wanted = Labelling(args.labelling)
        kept = tuple(c for c in split.train if c.labelling is wanted)
        if not kept:
            print(
                f"no {args.labelling}-labelled chips in the training split; "
                f"it holds {sorted({c.labelling.value for c in split.train})}",
                file=sys.stderr,
            )
            return 2
        split = Split(train=kept, validation=split.validation, discarded=split.discarded)

    print(split.summary())
    print()

    print("Fitting normalisation on the training split only...")
    normalisation = fit_normalisation(split.train)
    print(f"  mean {tuple(round(v, 2) for v in normalisation.mean)} dB")
    print(f"  std  {tuple(round(v, 2) for v in normalisation.std)} dB\n")

    dataset = _TorchDataset(
        Sen1Floods11Dataset(
            split.train,
            normalisation,
            crop_size=args.crop,
            seed=args.seed,
            include_prior=args.prior,
        )
    )
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, num_workers=0)

    # Warm the cache up to its budget before the timer starts, and say what fits.
    # Without this line a 4,096-chip run looks mysteriously slower per epoch than a
    # 308-chip one at the same per-chip cost, and the reason -- most chips are
    # being re-read from disk every epoch -- is invisible.
    for index in range(len(dataset.inner)):
        dataset.inner[index]
        if dataset.inner.cached_chips <= index:
            break
    cached = dataset.inner.cached_chips
    print(
        f"cache: {cached} of {len(split.train)} chips held in memory"
        + ("" if cached == len(split.train) else "; the rest are re-read each epoch")
    )

    in_channels = len(MODEL_BANDS) + (1 if args.prior else 0)
    model = UNet(in_channels=in_channels, base_channels=args.base_channels, depth=args.depth)
    print(
        f"UNet: {model.parameter_count:,} parameters, depth {args.depth}, "
        f"{in_channels} input channels"
        + (" (VV, VH, JRC permanent-water prior)" if args.prior else " (VV, VH)")
        + "\n"
    )

    if args.init_from is not None:
        if not args.init_from.is_file():
            print(f"--init-from given but {args.init_from} does not exist", file=sys.stderr)
            return 2
        pretrained = torch.load(args.init_from, weights_only=True, map_location="cpu")
        if pretrained["architecture"] != {
            "in_channels": in_channels,
            "base_channels": args.base_channels,
            "depth": args.depth,
        }:
            print(
                "REFUSING to initialise from a different architecture:\n"
                f"  checkpoint {pretrained['architecture']}\n"
                f"  this run   in_channels={in_channels}, "
                f"base_channels={args.base_channels}, depth={args.depth}\n"
                "load_state_dict would either raise or, worse, load the subset of "
                "layers whose shapes happen to match and leave the rest random.",
                file=sys.stderr,
            )
            return 2
        model.load_state_dict(pretrained["state_dict"])

        # The pretrained weights encode the scaling they were trained under, so
        # the fine-tune adopts it rather than refitting on its own smaller split.
        # Refitting would shift every input distribution the moment stage two
        # begins -- the features would be reading a different unit than the one
        # they learned, which looks like catastrophic forgetting and is not.
        adopted = Normalisation.from_dict(pretrained["normalisation"])
        if adopted != normalisation:
            print(
                f"adopting the pretrained normalisation from {args.init_from}:\n"
                f"  fitted here  mean {tuple(round(v, 2) for v in normalisation.mean)}\n"
                f"  adopted      mean {tuple(round(v, 2) for v in adopted.mean)}"
            )
            normalisation = adopted
            dataset.inner.normalisation = normalisation
            dataset.inner.clear_cache()
        print(
            f"initialised from {args.init_from} "
            f"(epoch {pretrained.get('epoch', '?')}, "
            f"validation IoU {pretrained.get('validation_iou', float('nan')):.3f})\n"
        )

    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=args.epochs)

    args.out.mkdir(parents=True, exist_ok=True)
    history: list[EpochResult] = []
    best_iou = -1.0
    start_epoch = 1

    # Resuming restores the optimiser and scheduler as well as the weights.
    # Restoring weights alone is the classic half-resume: AdamW's moment estimates
    # restart from zero and the cosine schedule restarts at its peak learning rate,
    # so the first epoch after a resume takes a large step in a random direction and
    # undoes several epochs of progress. It looks like instability rather than a
    # bug, which is why it is easy to live with for a long time.
    last_path = args.out / "last.pt"
    if args.resume:
        if not last_path.is_file():
            print(f"--resume given but {last_path} does not exist", file=sys.stderr)
            return 2
        state = torch.load(last_path, weights_only=True)
        model.load_state_dict(state["state_dict"])
        optimiser.load_state_dict(state["optimiser"])
        scheduler.load_state_dict(state["scheduler"])
        start_epoch = state["epoch"] + 1
        best_iou = state["best_iou"]
        history = [EpochResult(**h) for h in state["history"]]

        saved = Normalisation.from_dict(state["normalisation"])
        if saved != normalisation:
            print(
                "REFUSING to resume: the normalisation constants in the checkpoint "
                "differ from those fitted now, which means the training data or the "
                "split has changed. Continuing would train a model on one "
                "distribution using another's statistics.",
                file=sys.stderr,
            )
            return 2

        if start_epoch > args.epochs:
            # Falls through to the report rather than returning. A finished run
            # asked for its numbers should produce them: the evaluation is the
            # deliverable, and the first version of this exited here, which meant a
            # run whose final report was interrupted could never be reported at all
            # without retraining it.
            print(f"already trained {state['epoch']} epochs; reporting only\n")
        else:
            print(f"resuming from epoch {start_epoch} (best IoU so far {best_iou:.3f})\n")

    print(f"{'epoch':>5} {'loss':>8} {'val IoU':>8} {'val F1':>8} {'sec':>6}")
    print("-" * 40)

    for epoch in range(start_epoch, args.epochs + 1):
        started = time.time()
        model.train()
        losses = []
        for x, y, w in loader:
            optimiser.zero_grad(set_to_none=True)
            loss = masked_bce_dice_loss(model(x), y, w)
            loss.backward()
            # Sixty chips and a small batch make for noisy gradients; clipping stops
            # one unlucky all-water crop from taking a step that undoes an epoch.
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimiser.step()
            losses.append(float(loss.item()))
        scheduler.step()

        # The last epoch is always scored: a run whose reported number came from
        # five epochs ago would be quietly wrong, and the "best" checkpoint would be
        # selected on an incomplete picture.
        should_validate = epoch % args.val_every == 0 or epoch == args.epochs
        iou, f1 = (
            evaluate(model, split.validation, normalisation)
            if should_validate
            else (float("nan"), float("nan"))
        )
        result = EpochResult(
            epoch=epoch,
            train_loss=float(np.mean(losses)),
            validation_iou=iou,
            validation_f1=f1,
            seconds=time.time() - started,
        )
        history.append(result)
        scores = f"{iou:8.3f} {f1:8.3f}" if should_validate else f"{'-':>8} {'-':>8}"
        print(f"{epoch:5d} {result.train_loss:8.4f} {scores} {result.seconds:6.1f}")

        # Selected on validation IoU, which is held-out by region. Selecting on
        # training loss would pick the most memorised epoch.
        # Written every epoch so a killed run resumes from where it stopped, as
        # opposed to best.pt which is written only on improvement.
        torch.save(
            {
                "state_dict": model.state_dict(),
                "optimiser": optimiser.state_dict(),
                "scheduler": scheduler.state_dict(),
                "normalisation": normalisation.to_dict(),
                "epoch": epoch,
                # max() over the *validated* score only. Writing `iou` here
                # unconditionally poisoned best_iou with NaN on every unvalidated
                # epoch, and because every comparison against NaN is False, the
                # best checkpoint then stopped being written entirely -- silently,
                # since training carried on looking healthy.
                "best_iou": max(best_iou, iou) if should_validate else best_iou,
                "history": [asdict(h) for h in history],
            },
            last_path,
        )

        if should_validate and iou > best_iou:
            best_iou = iou
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "normalisation": normalisation.to_dict(),
                    "architecture": {
                        "in_channels": model.in_channels,
                        "base_channels": args.base_channels,
                        "depth": args.depth,
                    },
                    "epoch": epoch,
                    "validation_iou": iou,
                    "seed": args.seed,
                    "train_regions": sorted({c.region for c in split.train}),
                    "validation_regions": sorted({c.region for c in split.validation}),
                },
                args.out / "best.pt",
            )

    print()
    checkpoint = torch.load(args.out / "best.pt", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])

    model_iou, model_f1 = evaluate(model, split.validation, normalisation)
    base_iou, base_f1, base_strata = baseline_scores(split.validation)
    model_strata = model_stratified(model, split.validation, normalisation)

    print("=" * 62)
    print(f"HELD-OUT REGIONS: {', '.join(sorted({c.region for c in split.validation}))}")
    print(f"{len(split.validation)} chips, never seen in training\n")
    print(f"{'':<22}{'IoU':>10}{'F1':>10}")
    print(f"{'deterministic baseline':<22}{base_iou:>10.3f}{base_f1:>10.3f}")
    print(f"{'U-Net':<22}{model_iou:>10.3f}{model_f1:>10.3f}")
    delta = model_iou - base_iou
    print(f"{'difference':<22}{delta:>+10.3f}")

    print("\nstratified by water content (IoU) -- ADR-0007 D13:")
    print(f"{'water in chip':<16}{'baseline':>10}{'U-Net':>10}")
    for key in ("<1%", "1-10%", "10-30%", ">30%"):
        if key in base_strata or key in model_strata:
            b = base_strata.get(key, float("nan"))
            m = model_strata.get(key, float("nan"))
            print(f"{key:<16}{b:>10.3f}{m:>10.3f}")

    if delta <= 0:
        print(
            "\nThe model does NOT beat the deterministic baseline on held-out "
            "regions.\nThat is the result. Report it; do not tune the split until "
            "it changes."
        )

    report = {
        "model": {"iou": model_iou, "f1": model_f1, "stratified_iou": model_strata},
        "baseline": {"iou": base_iou, "f1": base_f1, "stratified_iou": base_strata},
        "delta_iou": delta,
        "epochs": args.epochs,
        "seed": args.seed,
        "parameters": model.parameter_count,
        # Provenance a reviewer will ask for and that cannot be recovered from the
        # weights: what the model was fed, and what it was trained on.
        "in_channels": model.in_channels,
        "uses_permanent_water_prior": bool(args.prior),
        "training_labelling": args.labelling,
        "initialised_from": str(args.init_from) if args.init_from else None,
        "train_chips": len(split.train),
        "train_chips_hand": sum(1 for c in split.train if c.labelling is Labelling.HAND),
        "train_chips_weak": sum(1 for c in split.train if c.labelling is not Labelling.HAND),
        "discarded_chips": len(split.discarded),
        "train_regions": sorted({c.region for c in split.train}),
        "validation_regions": sorted({c.region for c in split.validation}),
        "validation_chips": [c.stem for c in split.validation],
        "history": [asdict(h) for h in history],
    }
    (args.out / "metrics.json").write_text(json.dumps(report, indent=2))
    print(f"\ncheckpoint  {args.out / 'best.pt'}")
    print(f"metrics     {args.out / 'metrics.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
