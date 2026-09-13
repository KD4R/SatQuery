# Evaluation report

**Generated, never hand-written.** Regenerate with:

```bash
python3 fetch_sen1floods11.py --split all --count 400
PYTHONPATH="$PWD" python ml/scripts/generate_report.py
```

No number about this subsystem may appear in a slide, a README or a demo
script unless it appears here first. A figure that exists only in prose is a
recollection, not a measurement.

| | |
|---|---|
| generated | 2026-09-13 12:45 UTC |
| code fingerprint | `dcffe203f08bb6e8` |
| dataset fingerprint | `0305c0a36ac41cd7` |
| chips scored | 395 of 400 |
| regions | Ghana, India, Mekong, Nigeria, Pakistan, Paraguay, Somalia, Spain, Sri-Lanka, USA |
| model | `artifacts/flood-unet/best.pt` |

The code fingerprint is a hash over the modules that can change a reported
number. CI recomputes it and fails if this report was produced by different
code — see `ml/scripts/check_report_fresh.py`. CI cannot verify the numbers
are right, because the chips are gitignored; it can verify they are not stale.

---

## Headline

Held out **India, Somalia** — 92 chips, never seen in training. Trained on 308 chips across Ghana, Mekong, Nigeria, Pakistan, Paraguay, Spain, Sri-Lanka, USA.

The split is by **region, not by chip**: Sen1Floods11 tiles come from a small
number of flood events, so a chip-level split lets a model score well by
recognising terrain it has already seen.

| method | pooled IoU | pooled F1 | mean per-chip IoU | mean per-chip F1 |
|---|---|---|---|---|
| deterministic baseline | 0.204 | 0.339 | 0.209 | 0.289 |
| U-Net | **0.421** | **0.593** | 0.259 | 0.359 |

**Do not quote accuracy for this task.** Water is 10.8% of the scorable pixels on this split, so a model that predicts no water anywhere scores 89.2% accuracy and 0.000 IoU. Every target of the form "N% accurate" below that figure is met by a model that does nothing. The scored methods above reach baseline 68.5%, U-Net 90.8% -- which is why IoU and F1 are the reported metrics.

1 of 92 chips is absent from the pooled baseline: Otsu found no separable threshold and the method abstained. An abstention is not a zero score, so those chips are excluded rather than counted as total failures (ADR-0007 D10).

---

## Stratified by water content

A single mean says as much about the sample's wet/dry mix as about the method
(ADR-0007 D13), so it is never reported alone.

| water in chip | chips | baseline IoU | U-Net IoU |
|---|---|---|---|
| <1% | 21 | 0.003 | 0.018 |
| 1-10% | 41 | 0.130 | 0.248 |
| 10-30% | 20 | 0.327 | 0.319 |
| >30% | 10 | 0.725 | 0.694 |

---

## By region

**Only the held-out rows measure generalisation.** The model trained on the
regions marked *trained*, so its score there is partly recall of what it has
already seen and must not be quoted as accuracy. They are shown anyway,
because a large gap between trained and held-out rows is the signal that a
model memorised rather than learned — which is what this table is for.

| region | chips | split | baseline IoU | U-Net IoU |
|---|---|---|---|---|
| Ghana | 48 | trained | 0.104 | 0.237 |
| India | 68 | **held out** | 0.255 | 0.319 |
| Mekong | 30 | trained | 0.531 | 0.581 |
| Nigeria | 18 | trained | 0.331 | 0.367 |
| Pakistan | 28 | trained | 0.141 | 0.177 |
| Paraguay | 67 | trained | 0.224 | 0.334 |
| Somalia | 24 | **held out** | 0.080 | 0.092 |
| Spain | 24 | trained | 0.261 | 0.372 |
| Sri-Lanka | 33 | trained | 0.202 | 0.272 |
| USA | 55 | trained | 0.140 | 0.281 |

Mean U-Net IoU is 0.318 on trained regions against 0.259 held out, a gap of +0.058. A large positive gap means memorisation; near zero means the model generalises about as well as it fits.

---

## What these numbers are not

- **Not calibrated.** Confidence is reported as `NOT_CALIBRATED` everywhere
  (ADR-0007 D5). A sigmoid output is a normalised score, not a probability.
- **Not a bi-temporal result.** Sen1Floods11 has no pre-event imagery, so this
  measures single-date water detection, not flood *change*. Issue #14.
- **Not comparable across reports with different dataset fingerprints.** The
  baseline moved from 0.242 to 0.189 between two runs purely because the
  validation set grew; the method was identical (D15).

