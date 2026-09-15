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
from ml.evaluation.segmentation import SegmentationMetrics, pool
from ml.geo.area import pixel_area_m2
from ml.io.preflight import PreflightError
from ml.io.raster import read_raster, reproject_to_area_safe_crs
from ml.pipeline.baseline import water_mask_single_date
from ml.pipeline.learned import predict_water_mask
from ml.pipeline.postprocess import postprocess_water_mask
from ml.sar.change import ThresholdError
from ml.scripts.evaluate_baseline import _load_label_onto
from ml.training.splits import Chip, Labelling, discover_chips, split_by_region
from ml.scripts.report_freshness import code_fingerprint, write_sidecar

DEFAULT_ROOT = Path("data/sen1floods11")
DEFAULT_OUT = Path("reports/evaluation.md")
DEFAULT_MODEL = Path("artifacts/flood-unet/best.pt")
MODEL_ROOT = Path("artifacts")


def discover_models(root: Path, single: Path | None) -> dict[str, Path]:
    """Every ``<root>/<name>/best.pt``, or just the one the caller named.

    Scored together in one process, because that is the only way two models'
    numbers are comparable: same chips, same grid, same code. D15 is the record of
    what happens otherwise -- the baseline appeared to drop from 0.242 to 0.189
    when nothing about it had changed except which chips it saw.
    """
    if single is not None:
        return {single.parent.name: single} if single.is_file() else {}
    if not root.is_dir():
        return {}
    return {path.parent.name: path for path in sorted(root.glob("*/best.pt"))}


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


def load_models(paths: dict[str, Path]) -> dict[str, tuple]:
    """Load every named checkpoint, skipping the ones that cannot be read.

    A checkpoint that fails to load is reported and dropped rather than aborting
    the run: one unreadable experiment should not cost the comparison between the
    others, which is the reason to score several in the first place.
    """
    loaded: dict[str, tuple] = {}
    for name, path in paths.items():
        if not path.is_file():
            continue
        try:
            import torch

            from ml.models.unet import UNet
            from ml.training.dataset import Normalisation

            state = torch.load(path, weights_only=True, map_location="cpu")
            model = UNet(**state["architecture"])
            model.load_state_dict(state["state_dict"])
            model.eval()
            loaded[name] = (model, Normalisation.from_dict(state["normalisation"]))
        except Exception as error:  # noqa: BLE001
            print(f"model {name} unavailable ({error}); omitting it", file=sys.stderr)
    return loaded


def evaluate_all(chips: tuple[Chip, ...], model_paths: dict[str, Path]):
    """Score the baseline and every model on the same chips, in one pass.

    One pass, not one run per model. Two models scored in separate runs are two
    numbers measured on whatever each run happened to see, and comparing them is
    the mistake D15 records -- there the baseline appeared to fall from 0.242 to
    0.189 when nothing about it had changed but the validation set. Everything
    compared in this report is scored against the same chips, on the same grid, by
    the same code, in the same process.
    """
    models = load_models(model_paths)

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
            base = None
            base_iou = base_f1 = float("nan")

        row = {
            "stem": chip.stem,
            "region": chip.region,
            "water_percent": water,
            "bucket": bucket_for(water),
            "baseline_iou": base_iou,
            "baseline_f1": base_f1,
            # The counts, not just the ratios. Pooling needs them, and a ratio
            # cannot be un-averaged back into one.
            "baseline_counts": _counts(base),
        }

        for name, (model, normalisation) in models.items():
            # Predicted on the SAME reprojected raster the baseline was scored on.
            # Scoring them on different grids is how a comparison silently becomes
            # meaningless -- see ml/pipeline/learned.py.
            predicted = predict_water_mask(model, normalisation, raster)
            cleaned = postprocess_water_mask(predicted, pixel_area_m2=per_pixel).mask
            scored = confusion(cleaned, truth, ignore_value=IGNORE)
            row[f"iou::{name}"] = scored.intersection_over_union
            row[f"f1::{name}"] = scored.f1
            row[f"counts::{name}"] = _counts(scored)

        rows.append(row)
    return rows, tuple(models)


def _counts(metrics) -> dict[str, int] | None:
    """The four confusion counts, or None when the method produced no mask.

    None rather than zeros: a method that abstained on a chip did not score zero
    there, and folding zeros into a pooled total would quietly credit it with a
    perfect true-negative run over a chip it never looked at.
    """
    if metrics is None:
        return None
    return {
        "true_positive": metrics.true_positive,
        "false_positive": metrics.false_positive,
        "false_negative": metrics.false_negative,
        "true_negative": metrics.true_negative,
        "ignored_pixels": metrics.ignored_pixels,
    }


def _best(rows, names: tuple[str, ...]) -> str | None:
    """The model with the highest pooled IoU, or None when none was scored."""
    pooled = {name: _pooled(rows, f"counts::{name}") for name in names}
    pooled = {name: p for name, p in pooled.items() if p is not None}
    if not pooled:
        return None
    return max(pooled, key=lambda n: pooled[n].intersection_over_union)


def _pooled(rows, key: str):
    """Pool the per-chip counts for one method, or None if it never scored."""
    collected = [SegmentationMetrics(**r[key]) for r in rows if r.get(key) is not None]
    return pool(collected) if collected else None


def _headline(scored, names: tuple[str, ...]) -> list[str]:
    """Both aggregations, side by side, with the number that makes them readable.

    Two IoUs for the same model on the same chips is not indecision. Averaging
    per-chip IoU gives a 512x512 tile holding nine water pixels the same vote as a
    half-flooded one, and most of this benchmark is nearly dry -- so the mean is
    dominated by chips where one misplaced pixel swings the score. Pooling weights
    each chip by how much water was there to find, and is the aggregation the
    Sen1Floods11 literature reports. They differ by roughly a factor of two here.

    Quoting either alone, without saying which, is how two people end up arguing
    about the same model.

    Accuracy is printed for one reason: to be refused. See the note under the table.
    """
    baseline = _pooled(scored, "baseline_counts")
    models = {name: _pooled(scored, f"counts::{name}") for name in names}
    models = {name: m for name, m in models.items() if m is not None}

    base_iou = fmt(baseline.intersection_over_union) if baseline else "n/a"
    base_f1 = fmt(baseline.f1) if baseline else "n/a"
    lines = [
        "| method | pooled IoU | pooled F1 | mean per-chip IoU | mean per-chip F1 |",
        "|---|---|---|---|---|",
        f"| deterministic baseline | {base_iou} | {base_f1} "
        f"| {fmt(mean([r['baseline_iou'] for r in scored]))} "
        f"| {fmt(mean([r['baseline_f1'] for r in scored]))} |",
    ]
    # Best pooled IoU in bold, so the table has one obvious answer to "which won"
    # without the reader recomputing it.
    best = max(models, key=lambda n: models[n].intersection_over_union, default=None)
    for name, pooled in models.items():
        emphasis = "**" if name == best else ""
        lines.append(
            f"| {name} | {emphasis}{fmt(pooled.intersection_over_union)}{emphasis} "
            f"| {emphasis}{fmt(pooled.f1)}{emphasis} "
            f"| {fmt(mean([r[f'iou::{name}'] for r in scored]))} "
            f"| {fmt(mean([r[f'f1::{name}'] for r in scored]))} |"
        )

    model = models.get(best) if best else None
    reference = model if model is not None else baseline
    if reference is not None:
        floor = 1.0 - reference.prevalence
        lines += [
            "",
            "**Do not quote accuracy for this task.** Water is "
            f"{reference.prevalence:.1%} of the scorable pixels on this split, so a "
            f"model that predicts no water anywhere scores {floor:.1%} accuracy and "
            '0.000 IoU. Every target of the form "N% accurate" below that figure is '
            "met by a model that does nothing. The scored methods above reach "
            + ", ".join(
                f"{name} {m.accuracy:.1%}"
                for name, m in ((("baseline", baseline),) + tuple(models.items()))
                if m is not None
            )
            + " -- which is why IoU and F1 are the reported metrics.",
        ]

    missing = sum(1 for r in scored if r.get("baseline_counts") is None)
    if missing:
        lines += [
            "",
            f"{missing} of {len(scored)} chips "
            f"{'is' if missing == 1 else 'are'} absent from the pooled baseline: "
            "Otsu found no separable threshold and the method abstained. An "
            "abstention is not a zero score, so those chips are excluded rather "
            "than counted as total failures (ADR-0007 D10).",
        ]
    return lines


def mean(values) -> float:
    finite = [v for v in values if not np.isnan(v)]
    return float(np.mean(finite)) if finite else float("nan")


def fmt(value: float) -> str:
    return "—" if np.isnan(value) else f"{value:.3f}"


def render(rows, *, names, chips, split, code_hash, model_paths) -> str:
    by_bucket = {b: [r for r in rows if r["bucket"] == b] for b in WATER_BUCKETS}
    regions = sorted({r["region"] for r in rows})
    # The stratified and per-region tables follow one model, not all of them: a
    # column per experiment makes both unreadable, and the question they answer
    # is "where does the best method still fail", not "rank the candidates".
    # The headline table above is where models are compared.
    focus = _best(rows, names)

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
        (
            "| models | " + ", ".join(f"`{n}` (`{model_paths[n]}`)" for n in names) + " |"
            if names
            else "| models | none — baseline only |"
        ),
        f"| tables below follow | `{focus}` |" if focus else "| tables below follow | — |",
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

    lines += _headline(scored, names)
    lines += ["", "---", "", "## Stratified by water content", ""]

    lines += [
        "A single mean says as much about the sample's wet/dry mix as about the method",
        "(ADR-0007 D13), so it is never reported alone.",
        "",
        "| water in chip | chips | baseline IoU | " + (f"{focus} IoU |" if focus else ""),
        "|---|---|---|" + ("---|" if focus else ""),
    ]
    for bucket in WATER_BUCKETS:
        group = [r for r in by_bucket[bucket] if held_out is None or r["stem"] in held_out]
        if not group:
            continue
        row = f"| {bucket} | {len(group)} | {fmt(mean([r['baseline_iou'] for r in group]))} |"
        if focus:
            row += f" {fmt(mean([r[f'iou::{focus}'] for r in group]))} |"
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
        "| region | chips | split | baseline IoU |" + (f" {focus} IoU |" if focus else ""),
    ]
    lines.append("|---|---|---|---|" + ("---|" if focus else ""))

    train_regions = {c.region for c in split.train} if split is not None else set()
    for region in regions:
        group = [r for r in rows if r["region"] == region]
        where = "trained" if region in train_regions else "**held out**"
        row = (
            f"| {region} | {len(group)} | {where} | "
            f"{fmt(mean([r['baseline_iou'] for r in group]))} |"
        )
        if focus:
            row += f" {fmt(mean([r[f'iou::{focus}'] for r in group]))} |"
        lines.append(row)

    if focus and train_regions:
        trained = [r for r in rows if r["region"] in train_regions]
        held = [r for r in rows if r["region"] not in train_regions]
        on_train = mean([r[f"iou::{focus}"] for r in trained])
        on_held = mean([r[f"iou::{focus}"] for r in held])
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
    parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="score exactly this checkpoint and no other. Without it every model "
        "under --models is scored, which is usually what you want: two models "
        "compared from separate runs are two numbers measured on whatever each "
        "run happened to see (ADR-0007 D15).",
    )
    parser.add_argument(
        "--models",
        type=Path,
        default=MODEL_ROOT,
        help=f"directory of <name>/best.pt checkpoints (default {MODEL_ROOT})",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    try:
        discovered = discover_chips(args.root)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    # HAND-LABELLED ONLY, and this filter is the whole safety property of the file.
    #
    # It is not a preference. Every figure in this report is quoted as accuracy, so
    # a chip scored against automatically derived labels would be reporting how
    # well the model imitates Otsu -- presented in the same table, in the same
    # column, indistinguishable from a measurement against ground truth.
    #
    # This is not hypothetical. The weakly-labelled fetch landed while this script
    # still scored everything `discover_chips` returned, and one run silently grew
    # from 400 chips to 859 and added two whole regions of Otsu-scored rows to the
    # per-region table. Nothing failed; the numbers merely stopped meaning what the
    # column header said.
    chips = tuple(c for c in discovered if c.labelling is Labelling.HAND)
    weak = len(discovered) - len(chips)
    if weak:
        print(
            f"ignoring {weak} weakly-labelled chips: this report is measured "
            "against hand-drawn ground truth only",
            file=sys.stderr,
        )
    if not chips:
        print(
            f"no hand-labelled chips under {args.root}. The weakly-labelled set "
            "cannot be reported against -- fetch the hand-labelled set:\n"
            "    python3 fetch_sen1floods11.py --count 400",
            file=sys.stderr,
        )
        return 2

    try:
        split = split_by_region(chips)
    except ValueError:
        split = None

    model_paths = discover_models(args.models, args.model)
    print(
        f"scoring {len(chips)} chips against {len(model_paths)} model(s): "
        f"{', '.join(model_paths) or 'none'}...",
        file=sys.stderr,
    )
    rows, names = evaluate_all(chips, model_paths)
    if not rows:
        print("no chip produced a score; refusing to write an empty report", file=sys.stderr)
        return 1

    report = render(
        rows,
        names=names,
        chips=chips,
        split=split,
        code_hash=code_fingerprint(repo_root),
        model_paths=model_paths,
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
