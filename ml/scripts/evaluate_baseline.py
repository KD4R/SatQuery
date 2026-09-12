#!/usr/bin/env python3
"""Score the deterministic baseline against Sen1Floods11 hand labels.

This produces the only kind of accuracy claim this project is allowed to make: a
number measured on labelled data that anyone can reproduce by running this script.

    python ml/scripts/evaluate_baseline.py

WHAT IT REFUSES TO DO
---------------------
There is no synthetic fallback and no partial run. If the chips are not on disk
the script says so and exits non-zero, because a benchmark that quietly evaluates
against something other than the benchmark is worse than no benchmark. Get the
data with ``fetch_sen1floods11.py`` first -- and note that it must be run from a
normal shell, since the sandboxes used during development cannot reach Google
Cloud Storage.

WHAT IT COMPARES
----------------
Three masks per chip, all on the label grid:

    ours        this package's baseline: Otsu on VV, water below threshold
    theirs      S1OtsuLabelHand, the dataset authors' own Otsu baseline
    truth       LabelHand, drawn by hand

Scoring against ``truth`` says whether the method works. Scoring ours against
theirs says whether *our implementation* of the method is right, which is a
different question and the one a reviewer should ask first: a large disagreement
with a published implementation of the same algorithm points at our code, not at
the algorithm.

Chips whose labels are entirely no-data are not skipped. They are run, and the
abstention they produce is part of the result -- refusing to answer is a
behaviour worth measuring, not an inconvenience to filter out.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio

from ml.contracts.scene import BackscatterScale, Polarization
from ml.evaluation.segmentation import SEN1FLOODS11_IGNORE_VALUE, confusion
from ml.io.raster import read_raster
from ml.pipeline.baseline import water_mask_single_date
from ml.io.preflight import PreflightError
from ml.sar.change import ThresholdError

DEFAULT_ROOT = Path("data/sen1floods11")


def _load_label(path: Path) -> np.ndarray:
    with rasterio.open(path) as source:
        label: np.ndarray = source.read(1)
    return label


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--polarization",
        default="VV",
        choices=[p.value for p in Polarization],
        help="band to threshold (default VV -- co-pol is the conventional choice)",
    )
    args = parser.parse_args()

    scenes = sorted((args.root / "S1Hand").glob("*_S1Hand.tif"))
    if not scenes:
        print(
            f"No chips under {args.root.resolve()}.\n\n"
            "Fetch them first, from a normal shell:\n"
            "    python3 fetch_sen1floods11.py --count 60\n\n"
            "Refusing to evaluate against anything else.",
            file=sys.stderr,
        )
        return 2

    polarization = Polarization(args.polarization)
    print(f"{len(scenes)} chips, thresholding {polarization.value}\n")

    header = f"{'chip':<22} {'outcome':<10} {'thresh':>7} {'IoU':>6} {'F1':>6} {'vs theirs':>10}"
    print(header)
    print("-" * len(header))

    scored: list[tuple[float, float]] = []
    agreements: list[float] = []
    abstained: list[tuple[str, str]] = []

    for scene_path in scenes:
        stem = scene_path.name.replace("_S1Hand.tif", "")
        truth = _load_label(args.root / "LabelHand" / f"{stem}_LabelHand.tif")

        raster = read_raster(
            scene_path,
            declared_band_order=(Polarization.VV, Polarization.VH),
            declared_scale=BackscatterScale.DECIBEL,
        )

        try:
            detection = water_mask_single_date(raster, polarization=polarization)
        except (PreflightError, ThresholdError) as error:
            reason = type(error).__name__
            abstained.append((stem, str(error)))
            print(f"{stem:<22} {'ABSTAIN':<10} {'-':>7} {'-':>6} {'-':>6} {reason:>10}")
            continue

        # An all-no-data chip has nothing to score even when a threshold exists.
        if not np.any(truth != SEN1FLOODS11_IGNORE_VALUE):
            print(
                f"{stem:<22} {'no labels':<10} {detection.threshold_db:7.2f} "
                f"{'-':>6} {'-':>6} {'-':>10}"
            )
            continue

        metrics = confusion(detection.mask, truth, ignore_value=SEN1FLOODS11_IGNORE_VALUE)

        theirs_path = args.root / "S1OtsuLabelHand" / f"{stem}_S1OtsuLabelHand.tif"
        if theirs_path.is_file():
            theirs = _load_label(theirs_path)
            against_theirs = confusion(
                detection.mask, theirs, ignore_value=SEN1FLOODS11_IGNORE_VALUE
            )
            agreement = against_theirs.intersection_over_union
            agreements.append(agreement)
            agreement_text = f"{agreement:10.3f}"
        else:
            agreement_text = f"{'-':>10}"

        scored.append((metrics.intersection_over_union, metrics.f1))
        print(
            f"{stem:<22} {'scored':<10} {detection.threshold_db:7.2f} "
            f"{metrics.intersection_over_union:6.3f} {metrics.f1:6.3f} {agreement_text}"
        )

    print("\n" + "=" * len(header))
    if scored:
        ious = np.array([s[0] for s in scored])
        f1s = np.array([s[1] for s in scored])
        print(f"chips scored          : {len(scored)}")
        print(f"mean IoU vs truth     : {np.nanmean(ious):.3f}   (median {np.nanmedian(ious):.3f})")
        print(f"mean F1  vs truth     : {np.nanmean(f1s):.3f}   (median {np.nanmedian(f1s):.3f})")
    else:
        print("chips scored          : 0")

    if agreements:
        print(f"mean IoU vs their Otsu: {np.nanmean(agreements):.3f}")

    if abstained:
        print(f"\nabstained on {len(abstained)} chip(s):")
        for stem, reason in abstained:
            print(f"  {stem}: {reason[:90]}")

    print(
        "\nMeans use nanmean deliberately: a chip where the positive class is absent "
        "from both truth and prediction has an undefined score, not a zero, and "
        "averaging a zero there would understate the method."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
