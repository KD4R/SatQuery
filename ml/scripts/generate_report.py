#!/usr/bin/env python3
"""Generate the committed evaluation report (P3-15).

    PYTHONPATH="$PWD" python ml/scripts/generate_report.py

Writes ``reports/evaluation.md``: the single file any number quoted about this
subsystem must come from. If a figure appears in a slide, a README or a demo
script and not here, it is not a measurement — it is a recollection.

THE PROBLEM THIS SOLVES, AND THE ONE IT CANNOT
-----------------------------------------------
Benchmark numbers drifting away from the code that produced them is the specific
defect that sank the previous iteration of this project: a demo script quoted five
figures that had never been generated. The obvious fix is a CI job that regenerates
the report and fails on any diff.

That does not work here. The chips are 533 MB and gitignored, so CI has no data to
regenerate from, and a gate that silently skips when data is absent is worse than
no gate — it reports green while checking nothing.

So the report carries a **fingerprint of the code that produced it**: a hash over
every module that can change a reported number. ``check_report_fresh.py``
recomputes that hash in CI and fails if it differs from the one recorded here.
CI cannot verify the numbers are *right*; it can verify they were produced by the
code currently on the branch, which is the part that silently rots.

The dataset is fingerprinted too — chip count, regions, and a hash of the sorted
chip names — so two reports can be compared and a change in the evaluation set
cannot be mistaken for a change in the method. ADR-0007 D15 exists because exactly
that confusion nearly happened.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from packages.contracts import BackscatterScale, Polarization
from ml.evaluation.segmentation import SEN1FLOODS11_IGNORE_VALUE as IGNORE
from ml.evaluation.segmentation import confusion
from ml.geo.area import pixel_area_m2
from ml.io.preflight import PreflightError
from ml.io.raster import read_raster, reproject_to_area_safe_crs
from ml.pipeline.baseline import water_mask_single_date
from ml.pipeline.learned import predict_water_mask
from ml.pipeline.postprocess import postprocess_water_mask
from ml.sar.change import ThresholdError
from ml.scripts.evaluate_baseline import _load_label_onto
from ml.training.splits import Chip, discover_chips, split_by_region
from ml.scripts.report_freshness import code_fingerprint, write_sidecar

DEFAULT_ROOT = Path("data/sen1floods11")
DEFAULT_OUT = Path("reports/evaluation.md")
DEFAULT_MODEL = Path("artifacts/flood-unet/best.pt")


WATER_BUCKETS = ("<1%", "1-10%", "10-30%", ">30%")


def dataset_fingerprint(chips: tuple[Chip, ...]) -> str:
    digest = hashlib.sha256()
    for stem in sorted(c.stem for c in chips):
        digest.update(stem.encode())
    return digest.hexdigest()[:16]


def bucket_for(water_percent: float) -> str:
    if water_percent < 1:
        return "<1%"
    if water_percent < 10:
        return "1-10%"
    if water_percent < 30:
        return "10-30%"
    return ">30%"


def evaluate_all(chips: tuple[Chip, ...], model_path: Path | None):
    """Score baseline and, if available, the model, on the same chips.

    Both in one pass so they cannot diverge: scoring them in separate runs is how
    a comparison ends up between two different validation sets, which is the
    mistake D15 records.
    """
    model = normalisation = None
    if model_path is not None and model_path.is_file():
        try:
            import torch

            from ml.models.unet import UNet
            from ml.training.dataset import Normalisation

            state = torch.load(model_path, weights_only=True, map_location="cpu")
            model = UNet(**state["architecture"])
            model.load_state_dict(state["state_dict"])
            model.eval()
            normalisation = Normalisation.from_dict(state["normalisation"])
        except Exception as error:  # noqa: BLE001
            print(f"model unavailable ({error}); reporting the baseline alone", file=sys.stderr)
            model = None

    rows = []
    for chip in sorted(chips, key=lambda c: c.stem):
        raster = reproject_to_area_safe_crs(
            read_raster(
                chip.scene,
                declared_band_order=(Polarization.VV, Polarization.VH),
                declared_scale=BackscatterScale.DECIBEL,
            )
        )
        truth = _load_label_onto(chip.label, raster, nodata=IGNORE)
        scorable = truth != IGNORE
        if not scorable.any():
            continue

        water = 100.0 * np.count_nonzero(truth[scorable] == 1) / scorable.sum()
        per_pixel = pixel_area_m2(raster.spec.pixel_size_m, raster.spec.crs)

        try:
            detection = water_mask_single_date(raster, polarization=Polarization.VV)
            base_mask = postprocess_water_mask(detection.mask, pixel_area_m2=per_pixel).mask
            base = confusion(base_mask, truth, ignore_value=IGNORE)
            base_iou, base_f1 = base.intersection_over_union, base.f1
        except (PreflightError, ThresholdError):
            base_iou = base_f1 = float("nan")

        model_iou = model_f1 = float("nan")
        if model is not None:
            # Predicted on the SAME reprojected raster the baseline was scored on.
            # Scoring the two on different grids is how a comparison silently
            # becomes meaningless -- see ml/pipeline/learned.py.
            predicted = predict_water_mask(model, normalisation, raster)
            cleaned = postprocess_water_mask(predicted, pixel_area_m2=per_pixel).mask
            scored = confusion(cleaned, truth, ignore_value=IGNORE)
            model_iou, model_f1 = scored.intersection_over_union, scored.f1

        rows.append(
            {
                "stem": chip.stem,
                "region": chip.region,
                "water_percent": water,
                "bucket": bucket_for(water),
                "baseline_iou": base_iou,
                "baseline_f1": base_f1,
                "model_iou": model_iou,
                "model_f1": model_f1,
            }
        )
    return rows, model is not None


def mean(values) -> float:
    finite = [v for v in values if not np.isnan(v)]
    return float(np.mean(finite)) if finite else float("nan")


def fmt(value: float) -> str:
    return "—" if np.isnan(value) else f"{value:.3f}"


def render(rows, *, has_model, chips, split, code_hash, model_path) -> str:
    by_bucket = {b: [r for r in rows if r["bucket"] == b] for b in WATER_BUCKETS}
    regions = sorted({r["region"] for r in rows})

    lines = [
        "# Evaluation report",
        "",
        "**Generated, never hand-written.** Regenerate with:",
        "",
        "```bash",
        "python3 fetch_sen1floods11.py --split all --count 400",
        'PYTHONPATH="$PWD" python ml/scripts/generate_report.py',
        "```",
        "",
        "No number about this subsystem may appear in a slide, a README or a demo",
        "script unless it appears here first. A figure that exists only in prose is a",
        "recollection, not a measurement.",
        "",
        "| | |",
        "|---|---|",
        f"| generated | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} |",
        f"| code fingerprint | `{code_hash}` |",
        f"| dataset fingerprint | `{dataset_fingerprint(chips)}` |",
        f"| chips scored | {len(rows)} of {len(chips)} |",
        f"| regions | {', '.join(regions)} |",
        f"| model | `{model_path}` |" if has_model else "| model | none — baseline only |",
        "",
        "The code fingerprint is a hash over the modules that can change a reported",
        "number. CI recomputes it and fails if this report was produced by different",
        "code — see `ml/scripts/check_report_fresh.py`. CI cannot verify the numbers",
        "are right, because the chips are gitignored; it can verify they are not stale.",
        "",
        "---",
        "",
        "## Headline",
        "",
    ]

    if split is not None:
        lines += [
            f"Held out **{', '.join(sorted({c.region for c in split.validation}))}** — "
            f"{len(split.validation)} chips, never seen in training. Trained on "
            f"{len(split.train)} chips across "
            f"{', '.join(sorted({c.region for c in split.train}))}.",
            "",
            "The split is by **region, not by chip**: Sen1Floods11 tiles come from a small",
            "number of flood events, so a chip-level split lets a model score well by",
            "recognising terrain it has already seen.",
            "",
        ]

    held_out = {c.stem for c in split.validation} if split is not None else None
    scored = [r for r in rows if held_out is None or r["stem"] in held_out]

    lines += [
        "| method | IoU | F1 |",
        "|---|---|---|",
        f"| deterministic baseline | {fmt(mean([r['baseline_iou'] for r in scored]))} "
        f"| {fmt(mean([r['baseline_f1'] for r in scored]))} |",
    ]
    if has_model:
        lines.append(
            f"| U-Net | **{fmt(mean([r['model_iou'] for r in scored]))}** "
            f"| **{fmt(mean([r['model_f1'] for r in scored]))}** |"
        )
    lines += ["", "---", "", "## Stratified by water content", ""]

    lines += [
        "A single mean says as much about the sample's wet/dry mix as about the method",
        "(ADR-0007 D13), so it is never reported alone.",
        "",
        "| water in chip | chips | baseline IoU | " + ("U-Net IoU |" if has_model else ""),
        "|---|---|---|" + ("---|" if has_model else ""),
    ]
    for bucket in WATER_BUCKETS:
        group = [r for r in by_bucket[bucket] if held_out is None or r["stem"] in held_out]
        if not group:
            continue
        row = f"| {bucket} | {len(group)} | {fmt(mean([r['baseline_iou'] for r in group]))} |"
        if has_model:
            row += f" {fmt(mean([r['model_iou'] for r in group]))} |"
        lines.append(row)

    lines += [
        "",
        "---",
        "",
        "## By region",
        "",
        "**Only the held-out rows measure generalisation.** The model trained on the",
        "regions marked *trained*, so its score there is partly recall of what it has",
        "already seen and must not be quoted as accuracy. They are shown anyway,",
        "because a large gap between trained and held-out rows is the signal that a",
        "model memorised rather than learned — which is what this table is for.",
        "",
        "| region | chips | split | baseline IoU |" + (" U-Net IoU |" if has_model else ""),
    ]
    lines.append("|---|---|---|---|" + ("---|" if has_model else ""))

    train_regions = {c.region for c in split.train} if split is not None else set()
    for region in regions:
        group = [r for r in rows if r["region"] == region]
        where = "trained" if region in train_regions else "**held out**"
        row = (
            f"| {region} | {len(group)} | {where} | "
            f"{fmt(mean([r['baseline_iou'] for r in group]))} |"
        )
        if has_model:
            row += f" {fmt(mean([r['model_iou'] for r in group]))} |"
        lines.append(row)

    if has_model and train_regions:
        trained = [r for r in rows if r["region"] in train_regions]
        held = [r for r in rows if r["region"] not in train_regions]
        on_train = mean([r["model_iou"] for r in trained])
        on_held = mean([r["model_iou"] for r in held])
        lines += [
            "",
            f"Mean U-Net IoU is {fmt(on_train)} on trained regions against "
            f"{fmt(on_held)} held out, a gap of {on_train - on_held:+.3f}. A large "
            "positive gap means memorisation; near zero means the model generalises "
            "about as well as it fits.",
        ]

    lines += [
        "",
        "---",
        "",
        "## What these numbers are not",
        "",
        "- **Not calibrated.** Confidence is reported as `NOT_CALIBRATED` everywhere",
        "  (ADR-0007 D5). A sigmoid output is a normalised score, not a probability.",
        "- **Not a bi-temporal result.** Sen1Floods11 has no pre-event imagery, so this",
        "  measures single-date water detection, not flood *change*. Issue #14.",
        "- **Not comparable across reports with different dataset fingerprints.** The",
        "  baseline moved from 0.242 to 0.189 between two runs purely because the",
        "  validation set grew; the method was identical (D15).",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    try:
        chips = discover_chips(args.root)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    try:
        split = split_by_region(chips)
    except ValueError:
        split = None

    print(f"scoring {len(chips)} chips...", file=sys.stderr)
    rows, has_model = evaluate_all(chips, args.model)
    if not rows:
        print("no chip produced a score; refusing to write an empty report", file=sys.stderr)
        return 1

    report = render(
        rows,
        has_model=has_model,
        chips=chips,
        split=split,
        code_hash=code_fingerprint(repo_root),
        model_path=args.model,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report)

    # The per-chip table stays out of the markdown -- 400 rows is not a document --
    # but it is written beside it so a surprising mean can be traced to a chip.
    (args.out.parent / "per_chip.json").write_text(json.dumps(rows, indent=2))

    # Per-module hashes, so a future staleness failure can name what moved
    # rather than only that something did. Diagnostics only -- the gate's
    # verdict still comes from the combined fingerprint written into the report.
    write_sidecar(repo_root)

    print(f"wrote {args.out} and {args.out.parent / 'per_chip.json'}", file=sys.stderr)
    subprocess.run(["git", "diff", "--stat", "--", str(args.out)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
