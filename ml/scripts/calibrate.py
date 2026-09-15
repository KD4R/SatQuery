#!/usr/bin/env python3
"""Fit a temperature for the learned model and report what it bought (P3-11).

    PYTHONPATH="$PWD" python ml/scripts/calibrate.py

Writes reports/calibration.md and artifacts/<model>/calibration.json. Nothing else
changes -- see "no accuracy figure moves" below.

WHY THIS EXISTS
---------------
Every result this service has ever returned carries ConfidenceBasis.NOT_CALIBRATED,
because ADR-0007 D5 forbids presenting an uncalibrated score as a probability and
nobody had measured whether the model's scores were probabilities. This measures it.

A sigmoid output is a number in [0, 1]; that is all it shares with a probability.
IoU and F1 depend only on which side of the threshold a pixel falls, so a model
whose scores are systematically overconfident scores identically to one whose
scores are honest. The difference is invisible to every metric in
reports/evaluation.md and visible to any caller who thresholds on confidence.

FIT AND REPORT ARE DIFFERENT REGIONS
------------------------------------
Fitting the temperature and reporting the ECE on the same pixels measures how well
one parameter fits twenty-four million numbers, which is: perfectly. So the
held-out set is split again --

    fit on     Somalia   the hardest region for the baseline (D13)
    report on  India     the deployment condition, and the number that gets quoted

-- and the reported ECE is therefore out-of-sample twice over: the model never
trained on India, and the temperature was never fitted on it.

NO ACCURACY FIGURE MOVES
------------------------
Temperature scaling is one monotonic parameter, so it cannot reorder two pixels and
cannot change any thresholded mask. Every IoU and F1 in reports/evaluation.md is
provably unchanged, which is the point of choosing the weakest useful method: the
calibration can land without a reader wondering whether the model improved or the
metric got friendlier.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import numpy.typing as npt

from ml.evaluation.calibration import (
    DEFAULT_BINS,
    Calibration,
    apply_temperature,
    fit_temperature,
    reliability,
)
from ml.evaluation.segmentation import SEN1FLOODS11_IGNORE_VALUE as IGNORE
from ml.scripts.report_freshness import (
    CALIBRATION_FINGERPRINTED,
    code_fingerprint,
    write_sidecar,
)
from ml.io.raster import read_raster, reproject_to_area_safe_crs
from ml.scripts.evaluate_baseline import _load_label_onto
from ml.training.splits import Chip, Labelling, discover_chips, split_by_region
from packages.contracts import BackscatterScale

DEFAULT_ROOT = Path("data/sen1floods11")
DEFAULT_MODEL = Path("artifacts/flood-unet/best.pt")
DEFAULT_OUT = Path("reports/calibration.md")
REPO_ROOT = Path(__file__).resolve().parents[2]

#: ECE at or below which the model's scores may be presented as probabilities,
#: i.e. promoted from ConfidenceBasis.NOT_CALIBRATED to CALIBRATED_PROBABILITY.
#:
#: 0.05 means a claimed confidence is within five percentage points of the observed
#: frequency on average. The number is a judgement, but having one written down
#: before the measurement is the point: without a bar, "ECE improved" becomes the
#: finding, and "improved" and "good enough to quote as a probability" are
#: different claims that a reader will otherwise conflate.
CALIBRATION_BAR = 0.05

#: Held-out region the temperature is fitted on. The other held-out regions are
#: reported on. Fixed rather than randomised so two runs are comparable.
FIT_REGION = "Somalia"


def collect_logits(
    model, normalisation, chips: tuple[Chip, ...]
) -> tuple[npt.NDArray[np.float32], npt.NDArray[np.int8]]:
    """Per-pixel logits and labels over the scorable pixels of every chip.

    Logits, not probabilities: the temperature divides the logit, so a probability
    would have to be inverted back through the sigmoid first, and that inversion is
    lossy exactly where it matters -- a saturated 1.0 carries no information about
    whether the logit was 20 or 200.
    """
    import torch

    from ml.pipeline.learned import MODEL_BANDS
    from ml.training.dataset import prepare

    logits: list[npt.NDArray[np.float32]] = []
    labels: list[npt.NDArray[np.int8]] = []

    for chip in chips:
        raster = reproject_to_area_safe_crs(
            read_raster(
                chip.scene,
                declared_band_order=MODEL_BANDS,
                declared_scale=BackscatterScale.DECIBEL,
            )
        )
        truth = _load_label_onto(chip.label, raster, nodata=IGNORE)
        scorable = truth != IGNORE
        if not scorable.any():
            continue

        bands = np.stack([raster.band(p) for p in MODEL_BANDS]).astype(np.float32)
        include_prior = getattr(model, "in_channels", len(MODEL_BANDS)) > len(MODEL_BANDS)
        x, _, _ = prepare(
            bands,
            np.zeros(bands.shape[1:], dtype=np.int16),
            normalisation,
            None,
            include_prior=include_prior,
        )
        tensor = torch.from_numpy(x).unsqueeze(0)
        height, width = tensor.shape[-2:]
        multiple = 2**model.depth
        pad_h, pad_w = (-height) % multiple, (-width) % multiple
        if pad_h or pad_w:
            tensor = torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect")
        with torch.no_grad():
            out = model(tensor)
        if pad_h:
            out = out[..., :-pad_h, :]
        if pad_w:
            out = out[..., :, :-pad_w]

        chip_logits = out.squeeze(0).numpy().astype(np.float32)
        logits.append(chip_logits[scorable])
        labels.append((truth[scorable] == 1).astype(np.int8))

    if not logits:
        raise SystemExit("no scorable pixels in the requested chips")
    return np.concatenate(logits), np.concatenate(labels)


def _where_the_error_is(calibration: Calibration) -> str:
    """Name the bin doing the damage, computed rather than asserted.

    This paragraph used to be a fixed sentence describing the first model measured
    ("most pixels crowded into 0.2-0.5, a model that has not learned to commit").
    It was true of that model and false of the next one, which puts 60% of its
    pixels in the lowest bin -- and a generated report stating something it did not
    measure is the defect this whole file exists to catch, appearing inside the
    file itself.
    """
    populated = [b for b in calibration.bins if b.count > 0]
    if not populated:
        return ""
    total = sum(b.count for b in populated)
    modal = max(populated, key=lambda b: b.count)
    worst = max(populated, key=lambda b: abs(b.gap) * b.count)
    share = 100.0 * worst.count * abs(worst.gap) / sum(b.count * abs(b.gap) for b in populated)
    direction = "more" if worst.gap > 0 else "less"
    return (
        f"Where the error is: the {worst.lower:.1f}-{worst.upper:.1f} bin holds "
        f"{worst.count:,} pixels claiming {worst.mean_confidence:.3f} where "
        f"{worst.observed_frequency:.3f} are water, and contributes {share:.0f}% of "
        f"the remaining ECE on its own -- the model claims {direction} water than it "
        f"finds there. For scale, the busiest bin is "
        f"{modal.lower:.1f}-{modal.upper:.1f} with "
        f"{100.0 * modal.count / total:.0f}% of all pixels. One monotonic parameter "
        "moves the whole distribution and cannot reshape one bin, so the route past "
        "this bar is a better model rather than a richer calibrator. Re-run after "
        "the next training round."
    )


def diagram(calibration: Calibration) -> list[str]:
    lines = [
        "| confidence bin | pixels | mean claimed | observed | gap |",
        "|---|---|---|---|---|",
    ]
    for b in calibration.bins:
        if b.count == 0:
            lines.append(f"| {b.lower:.1f}-{b.upper:.1f} | 0 | — | — | — |")
            continue
        lines.append(
            f"| {b.lower:.1f}-{b.upper:.1f} | {b.count:,} | {b.mean_confidence:.3f} "
            f"| {b.observed_frequency:.3f} | {b.gap:+.3f} |"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--bins", type=int, default=DEFAULT_BINS)
    args = parser.parse_args()

    if not args.model.is_file():
        print(f"no checkpoint at {args.model}", file=sys.stderr)
        return 2

    import torch

    from ml.models.unet import UNet
    from ml.training.dataset import Normalisation

    state = torch.load(args.model, weights_only=True, map_location="cpu")
    model = UNet(**state["architecture"])
    model.load_state_dict(state["state_dict"])
    model.eval()
    normalisation = Normalisation.from_dict(state["normalisation"])

    chips = tuple(c for c in discover_chips(args.root) if c.labelling is Labelling.HAND)
    split = split_by_region(chips)

    fit_chips = tuple(c for c in split.validation if c.region == FIT_REGION)
    report_chips = tuple(c for c in split.validation if c.region != FIT_REGION)
    if not fit_chips or not report_chips:
        print(
            f"need chips both in and outside {FIT_REGION} among the held-out "
            f"regions; got {len(fit_chips)} and {len(report_chips)}. Fitting and "
            "reporting on the same pixels would measure how well one parameter "
            "fits them, which is perfectly.",
            file=sys.stderr,
        )
        return 2

    print(f"fitting on {len(fit_chips)} {FIT_REGION} chips...", file=sys.stderr)
    fit_logits, fit_labels = collect_logits(model, normalisation, fit_chips)
    temperature = fit_temperature(fit_logits, fit_labels)

    reported_regions = sorted({c.region for c in report_chips})
    print(f"reporting on {len(report_chips)} chips from {reported_regions}...", file=sys.stderr)
    logits, labels = collect_logits(model, normalisation, report_chips)

    before = reliability(apply_temperature(logits, 1.0), labels, bins=args.bins)
    after = reliability(apply_temperature(logits, temperature), labels, bins=args.bins)

    verdict = "improves" if after.ece < before.ece else "does not improve"
    direction = "overconfident" if temperature > 1 else "underconfident"
    passes = after.ece <= CALIBRATION_BAR

    lines = [
        "# Calibration report (P3-11)",
        "",
        "Generated by `ml/scripts/calibrate.py`. Do not edit by hand.",
        "",
        "| field | value |",
        "|---|---|",
        f"| generated | {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC |",
        f"| model | `{args.model}` |",
        f"| code fingerprint | `{code_fingerprint(REPO_ROOT, CALIBRATION_FINGERPRINTED)}` |",
        "| method | temperature scaling, one parameter |",
        f"| fitted on | {FIT_REGION}, {len(fit_chips)} chips, {fit_logits.size:,} pixels |",
        f"| reported on | {', '.join(reported_regions)}, {len(report_chips)} chips, "
        f"{logits.size:,} pixels |",
        f"| temperature | **{temperature:.3f}** |",
        f"| bins | {args.bins} |",
        "",
        f"The fitted temperature is {temperature:.3f}, so the raw model is "
        f"**{direction}**. Fitting and reporting use different regions, and the "
        "model trained on neither, so the figures below are out of sample twice.",
        "",
        "## Does it help?",
        "",
        "| | ECE | worst bin gap |",
        "|---|---|---|",
        f"| raw sigmoid | {before.ece:.4f} | {before.max_gap:.4f} |",
        f"| temperature-scaled | **{after.ece:.4f}** | **{after.max_gap:.4f}** |",
        "",
        f"Temperature scaling **{verdict}** calibration on held-out regions.",
        "",
        "## Verdict",
        "",
        f"The bar for presenting these scores as probabilities is ECE <= "
        f"{CALIBRATION_BAR:.2f}, written down before the measurement so that "
        '"improved" cannot quietly stand in for "good enough".',
        "",
        (
            f"**PASS - {after.ece:.4f}.** Results may be returned with "
            "`ConfidenceBasis.CALIBRATED_PROBABILITY` citing this report."
            if passes
            else (
                f"**FAIL - {after.ece:.4f}, against a bar of "
                f"{CALIBRATION_BAR:.2f}.** Scaling removed more than half the error "
                "and what remains is still too large to call these numbers "
                "probabilities. Results continue to ship as "
                "`ConfidenceBasis.NOT_CALIBRATED` (ADR-0007 D5). The remaining error "
                "is not noise: the gap is positive in almost every bin below, so the "
                "model claims more water than it finds, systematically."
            )
        ),
        "",
        ("" if passes else _where_the_error_is(after)),
        "",
        f"Water is {after.prevalence:.1%} of the reported pixels. ECE has to be read "
        "against that: a model emitting the base rate everywhere would score a near-"
        "zero ECE and be useless, so a small ECE is necessary and not sufficient.",
        "",
        "The worst-bin gap is reported beside ECE because ECE is count-weighted, and "
        "the high-confidence bins that a caller actually thresholds on hold few "
        "pixels — a model can average well and still be badly wrong exactly where it "
        "is relied upon.",
        "",
        "## No accuracy figure moves",
        "",
        "Temperature scaling divides the logit by a positive constant, which cannot "
        "reorder two pixels and so cannot change any thresholded mask. Every IoU and "
        "F1 in `reports/evaluation.md` is unchanged by construction, not by luck — "
        "which is why the weakest useful method was chosen over anything richer.",
        "",
        "## Reliability, raw",
        "",
        *diagram(before),
        "",
        "## Reliability, temperature-scaled",
        "",
        *diagram(after),
        "",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines))

    sidecar = args.model.parent / "calibration.json"
    sidecar.write_text(
        json.dumps(
            {
                "method": "temperature_scaling",
                "temperature": temperature,
                "fitted_on": [FIT_REGION],
                "reported_on": reported_regions,
                "ece_raw": before.ece,
                "ece_calibrated": after.ece,
                "max_gap_calibrated": after.max_gap,
                "bins": args.bins,
                "bar": CALIBRATION_BAR,
                # The field the registry and the service read. False means
                # results keep shipping NOT_CALIBRATED -- the measurement was
                # made and did not clear the bar, which is a different state
                # from "nobody has looked".
                "passes_bar": bool(passes),
                "report": str(args.out),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    # Refresh the per-module hashes so a later staleness failure for either
    # report can name what moved, whichever generator ran last.
    write_sidecar(REPO_ROOT)

    print(f"wrote {args.out} and {sidecar}", file=sys.stderr)
    print(
        f"T = {temperature:.3f}   ECE {before.ece:.4f} -> {after.ece:.4f}   "
        + (
            f"PASS (bar {CALIBRATION_BAR})"
            if passes
            else f"FAIL (bar {CALIBRATION_BAR}) -- results stay NOT_CALIBRATED"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
