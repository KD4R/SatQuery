# ADR-0007 — P3 ML foundation: contracts, dependencies and the decisions behind them

- **Status:** Accepted for the foundation commit; four items remain open and are listed at the end.
- **Date:** 2026-09-11
- **Owner:** P3 (Srushti)
- **Reviewer:** P1 (Siddharth)
- **Supersedes:** nothing. First ADR covering the ML subsystem.

---

## Context

The P3 Complete Engineering PRD specifies eighteen issues but, on audit, specifies
almost no engineering substance: all eighteen issue sheets carry identical values for
files-to-create, API, input, output, validation, security, observability and
acceptance criteria, and the implementation-steps field is the same five generic
strings in every case. Ten load-bearing technical decisions are absent entirely — no
dataset, no architecture, no accuracy target, no input contract, no split policy, no
latency budget.

The repository was also empty (a single 10-byte README, no git history), so the
spec's first implementation step — "inspect current contracts and neighbouring
service interfaces" — could not be performed. There were no contracts to inspect.

This ADR records the decisions taken to unblock the foundation, and marks clearly
which of them are provisional pending an answer from another role.

---

## Decisions

### D1 — Contracts are frozen pydantic models with no defaults

**Decision.** Every contract object inherits `Strict`: `extra="forbid"`,
`frozen=True`, `revalidate_instances="always"`. No field carries a default unless the
default is the only correct value.

**Reason.** Two consumers (P2 evidence, P4 geometry) and one producer (P4 discovery)
bind to these shapes. A default is how provenance goes missing; immutability is what
stops provenance being attached at validation and quietly replaced afterwards.

**Alternatives considered.** Dataclasses (no validation at the boundary, which is
where untrusted upstream data arrives). TypedDicts (no runtime enforcement at all).

---

### D2 — A number is only expressible as a `Measurement`

**Decision.** `Measurement` requires `produced_by`, `code_version`, `crs` and a
non-empty `derived_from`. `area_hectares` is the only function in this package
permitted to emit a user-visible area.

**Reason.** One function to audit, one function to test, one place the CRS guard
lives. If a second function starts returning hectares that is a defect regardless of
whether its arithmetic is right, because it doubles the surface that has to be
reviewed for the project's central claim.

**Consequence.** `value` is a `Decimal` built from a formatted string, so a figure
quoted in a report is exactly the figure computed. Quantised to 0.1 ha — finer than a
10 m pixel grid justifies already, and more digits would imply precision the
measurement does not have.

---

### D3 — Scale and band order are declared data, never inferred

**Decision.** `RasterSpec` carries `scale` (`POWER` / `AMPLITUDE` / `DECIBEL`) and
`band_order` explicitly. `ensure_decibel` takes the declared scale as a required
argument and converts only when needed. Nothing inspects pixel values to guess.

**Reason.** These are the two defects that produce a plausible wrong number rather
than an exception. Inferring either would sometimes be wrong, and a sometimes-wrong
silent conversion is worse than no conversion.

**This decision has already paid for itself.** The foundation commit documented
Sen1Floods11 as VH-then-VV, taken from secondary descriptions of the dataset. On
inspecting the actual v1.1 hand-labelled chips, every file carries band
descriptions `('VV', 'VH')`, and band 0 sits ~6 dB above band 1 on all twelve
chips measured -- the physical signature of co-polarised versus cross-polarised
backscatter. **The real order is VV(0) then VH(1).** No code changed as a result,
because no code ever inferred the order; only the prose was wrong. Had the loader
assumed the documented order, every channel would have been normalised with the
other channel's statistics and nothing would have crashed.

**Source.** Measured directly from the v1.1 chips with rasterio; the reference
repository is — S1 layer: 2 bands, Float32, VH(0) then
VV(1), units decibels; labels Int16 with −1 no-data / 0 not-water / 1 water.
<https://github.com/cloudtostreet/Sen1Floods11>

---

### D4 — ASF HyP3 is the recommended live SAR provider

**Decision.** Recommend ASF HyP3 over Microsoft Planetary Computer for the live path.
The provider allowlist in `preflight/raster.py` reflects this, with Copernicus Data
Space Ecosystem as secondary and Bhoonidhi retained for the sovereignty story.

**Reason.** HyP3 lets the requester choose the output scale explicitly (power,
amplitude or decibel), which removes the dB-versus-linear ambiguity *by construction*
rather than by assumption. It also emits float32 COGs already projected to UTM, which
is the projection area measurement requires — removing a reprojection step and a
class of error with it. It uses Copernicus GLO-30, the same DEM the terrain mask
wants.

Planetary Computer's `sentinel-1-rtc` collection page is JavaScript-rendered and its
units could not be verified; that question is avoided rather than answered.

**Source.** ASF HyP3 Sentinel-1 RTC Product Guide.
<https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/>
**Status.** Recommendation only — P4 owns provider choice. See OPEN-4.

---

### D5 — Confidence declares its basis, or reports nothing

**Decision.** `Confidence.basis` is one of `MODEL_AGREEMENT`,
`CALIBRATED_PROBABILITY`, `NOT_CALIBRATED`. A numeric value is permitted only for the
first two; `CALIBRATED_PROBABILITY` must cite its calibration report;
`MODEL_AGREEMENT` must carry the agreement IoU.

**Reason.** The P3 spec shows `"confidence": 0.94` with no stated origin. A confidence
figure is itself a number, and the premise of this subsystem is that a number must be
earned. A raw softmax is a normalised score, not a probability; presenting it as one
is the same class of defect as a fabricated hectare.

Calibration is configuration-specific — a model calibrated on Sen1Floods11 is not
calibrated for a different sensor, resolution or incidence angle. Outside the fitted
configuration the honest answer is `NOT_CALIBRATED`, and `Confidence.not_calibrated()`
exists so that the honest path is the easy one.

**Source.** Guo, Pleiss, Sun, Weinberger (2017), *On Calibration of Modern Neural
Networks*, arXiv:1706.04599 — temperature scaling, Expected Calibration Error,
reliability diagrams.

---

### D6 — Runtime dependencies are NumPy and pydantic only

**Decision.** No rasterio, pyproj, torch or scikit-image in this commit. Otsu is
implemented directly (it is short, and the test pins it against a synthetic bimodal
distribution). UTM zone selection is arithmetic rather than a database lookup.

**Reason.** The whole suite runs offline with no geospatial stack installed, in under
a second, on CPU. That keeps CI fast and makes the contracts validatable anywhere.

**Cost, recorded honestly.** `is_projected` uses an allowlist rather than a real CRS
lookup, so it is conservative: an unrecognised CRS is refused rather than assumed
projected. When pyproj arrives (needed for actual reprojection), widen it to
`pyproj.CRS(...).is_projected` and keep the allowlist as a fast path.

---

### D7 — Abstention is a value; no fixture ever substitutes for a result

**Decision.** Every analysis entry point returns `Analysis | Abstention`. The
`Analysis` type requires at least one measurement and at least one scene, so it
cannot represent a fabricated result. `Analysis.degraded_from` records when a fallback
method produced the answer, and is surfaced rather than hidden.

**Reason.** This directly replaces the "deterministic fixture fallback is allowed for
the SIH demo" authorised in three places in the P3 spec (section 15 agent prompt,
issue P3-14, section 10 failure-mode table). A fixture standing in for a failed
inference is a number no satellite produced, presented as though one did.

The two legitimate degraded behaviours are an abstention with a reason code, or a
fall back to the deterministic Otsu baseline *labelled as such*. Both are honest and
demonstrable; the second is strictly more impressive than a fixture.

**Status.** Conflicts with the spec as written. See OPEN-2.

---

### D8 — Add the deterministic baseline as a first-class path

**Decision.** The log-ratio + Otsu baseline is built before the learned model and
kept permanently, not discarded once the U-Net works.

**Reason.** It is the spec's largest omission — eighteen issues, six of them ML, and
no non-learned baseline anywhere. It needs no GPU, no labels and no training, so it
is the only path guaranteed to work early; it is the honest degraded mode for P3-14;
and the agreement between it and the learned model is the confidence basis P3-11
otherwise has no source for. A learned model with no baseline beside it is an
unfalsifiable claim.

---

### D9 — "Projected" is not sufficient for area; the guard is a positive allowlist

**Decision.** Two predicates, not one. `is_projected` asks whether a CRS measures in
linear units. `is_area_safe` asks whether multiplying two of those units yields a
defensible area, and is currently satisfied only by the WGS 84 UTM zones. Both live
in `packages/contracts/crs_policy.py`, which depends on nothing, so `contracts` and `geo` can share
the policy without depending on each other.

**Reason.** Review of the foundation commit found EPSG:3857 passing the area guard.
Web Mercator *is* projected — and conformal, with a scale factor of 1/cos(latitude)
in both axes, so an area from its pixel dimensions is inflated by 1/cos²(latitude):
about 3% at Kerala, 15% at 30 N, 100% at 60 N. Nothing raises, and the error grows
with distance from the equator, so it is largest where a reviewer has least intuition
for the right answer.

The same review found the `Measurement` CRS check was a *blacklist* of five
geographic identifiers. `EPSG:4258`, `EPSG:4283` and the literal string `"not-a-crs"`
all constructed valid physical measurements. A blacklist fails open, which is the
wrong direction for a safety guard: the set of unsafe CRSs is unbounded and the set
of safe ones is small and known.

**Consequence.** Adding a projection to `is_area_safe` is a deliberate reviewed act.
Equal-area families and the Indian national grids belong there once one is actually
used and its parameters are pinned — adding them speculatively would ship an
allowlist entry nobody has checked.

---

### D10 — Otsu does not detect whether there is anything to threshold

**Decision.** `otsu_threshold` raises only on too few valid samples or zero variance.
It does **not** claim to abstain on unimodal input, and carries no separability
parameter.

**Reason.** The foundation commit's docstring promised abstention on unimodal
distributions and did not deliver it: any non-constant distribution has finite
between-class variance somewhere, reaches `nanargmax`, and returns a split.

A gate was then attempted using Otsu's own goodness-of-fit, η = σ²_B / σ²_T, on the
theory that unimodal input would score low. Measured against the Sen1Floods11
hand-labelled chips and synthetic controls, it does not:

| Input | η |
|---|---|
| Pure Gaussian noise | 0.637 |
| Rayleigh speckle, dB domain | 0.622 |
| Weakly-separated bimodal | 0.637 |
| Well-separated bimodal | 0.973 |
| Sen1Floods11 chips **containing** water (n=6) | 0.533 – 0.721 |
| Sen1Floods11 chips with **no** water (n=6) | 0.512 – 0.675 |

The two real populations overlap almost entirely, and pure noise scores higher than
four of the six genuinely flooded chips. Any floor low enough to admit real floods
admits noise as well. Shipping the parameter regardless would have been worse than
shipping nothing, because a caller would set it and believe they were protected.

**Consequence, and it is a large one.** Single-date Otsu on raw VV backscatter is not
a flood detector, and this measurement is the evidence. Separability has to be judged
by agreement between methods that fail differently — which is what
`ConfidenceBasis.MODEL_AGREEMENT` exists for — or by the bi-temporal log-ratio, where
the quantity being thresholded is *change* rather than absolute backscatter. The
second is blocked on OPEN-4, since Sen1Floods11 ships no pre-event imagery.

Consistent with this, the dataset authors' own `S1OtsuLabelHand` baseline predicts
30,568 water pixels on `Ghana_1033830` where the hand labels mark 96,811.

---

### D11 — Review of the foundation commit found fourteen defects; all are fixed here

**Recorded because the pattern matters more than the individual bugs.** Six of the
fourteen were silent-wrong-number defects — the exact class this subsystem's README
claims to guard against, in the commit that made the claim. They were found by
automated review, not by the author, and not one produced an exception, a warning or
a visibly odd value.

Beyond D9 and D10 above: `pixel_area_m2` accepted infinite pixel dimensions
(`inf > 0` is true); `amplitude_to_db` squared before validating, so `-1` became a
clean `0 dB`; `confusion()` validated truth labels but not predictions, so a class ID
of `2` scored as water; `validate_finite_fraction` ignored finite no-data sentinels,
so a raster of `-9999` reported 100% valid; `f1` returned NaN where IoU returned 0.0,
deleting the worst samples from any average; `frozen=True` did not prevent in-place
mutation of `list` fields, so validated provenance stayed editable — the same
argument this role had just raised against another role's contract; `Confidence`
permitted a value outside its own interval and a `MODEL_AGREEMENT` value that
contradicted its IoU; and `s3` was an advertised URL scheme that could never validate.

**The conclusion drawn.** Guards that are asserted in prose are not guards. Each of
these now has a regression test in `ml/tests/test_review_findings.py` stating what
went wrong and why it was invisible, because the shared property of all fourteen is
that they passed review by a reader who had just written the trap list.

---

### D12 — Postprocessing is tuned for the ground, not for the score

**Decision.** The mask cleanup runs speckle removal, hole filling, minimum mapping
unit and permanent-water subtraction, in that order, with the MMU defaulting to
**0.5 ha** and permanent-water subtraction **on in production, off when scoring
against Sen1Floods11**.

**Two findings from measuring it rather than assuming it.**

**1. Subtracting permanent water makes the benchmark score worse, and is still
right.** Measured over nine chips:

| configuration | mean IoU |
|---|---|
| raw threshold mask | 0.187 |
| morphology only | 0.203 |
| morphology + MMU | **0.221** |
| morphology + MMU + permanent water | 0.194 |

The cause is not a bug. **65.5%** of JRC permanent-water pixels are also marked
water in Sen1Floods11's `LabelHand`, because Sen1Floods11 is a *surface-water*
benchmark, not a *flood-change* one. Subtracting the lake therefore removes true
positives from the score.

For the product the subtraction is unambiguously correct — a reservoir reported as
flooding is the single most damaging false positive this system can emit. So the
step stays on by default and the *evaluation* turns it off, with the flag named in
the output. Optimising it away because it costs 0.03 IoU would be tuning the
product to the benchmark instead of to the job.

**2. The MMU sweep exposes the detector, not the filter.**

| MMU ha | IoU | precision | recall |
|---|---|---|---|
| 0 | 0.203 | 0.294 | 0.696 |
| 0.5 | 0.221 | 0.322 | 0.661 |
| 2 | 0.243 | 0.356 | 0.609 |
| 5 | **0.252** | 0.373 | 0.577 |
| 50 | 0.215 | 0.349 | 0.363 |

IoU peaks near 5 ha. That is not the filter working — precision at 0 ha is 0.294,
so seven of every ten detected pixels are wrong, and deleting most of the mask
raises the average because most of the mask is noise. Recall falls monotonically
the whole way down.

A 5 ha minimum cannot see a flooded neighbourhood. It would buy 0.03 IoU on nine
chips and ship a system that misses the thing it exists to find, so the default is
0.5 ha — inside the 0.1–1 ha range Copernicus EMS rapid mapping uses, and about
the smallest patch a responder can act on separately. The precision is the learned
model's problem to fix; the MMU's job is to drop patches too small to act on. A
test pins the constant so that a future "optimisation" toward the score is visible
in review.

**Headline, corrected on more data.** The figures above were measured on nine
chips. On 57 chips across seven regions the same comparison gives **0.257 raw,
0.267 postprocessed** — a 4% relative gain, not 18%. The nine-chip result was
overfit to its sample, and the correction is recorded rather than quietly
substituted because the first number was already quoted in a commit message.

Postprocessing is still worth keeping — it removes false positives an operator
would otherwise have to explain, and the reporting it produces is what makes the
number auditable — but it is a tidying step, not an accuracy strategy.

---

### D13 — The baseline's failure is concentrated, not diffuse

**Finding.** Scored over 57 hand-labelled chips from seven regions, IoU is almost
entirely predicted by how much water the chip actually contains:

| water in chip | n | mean IoU |
|---|---|---|
| < 1% | 19 | **0.004** |
| 1–10% | 19 | 0.181 |
| 10–30% | 10 | 0.535 |
| > 30% | 9 | **0.704** |

The distribution is bimodal, not centred: 28 chips score below 0.05 and 13 score
above 0.6. Mean precision is 0.333 against mean recall of 0.728.

**Reading.** On a genuinely flooded scene the deterministic baseline is *good* —
IoU 0.70 is within reach of published supervised results. It fails catastrophically
on scenes with little or no water, and it fails in one specific way: Otsu always
splits a histogram, so on a dry scene it invents a flood. High recall with poor
precision is exactly that signature. The overall mean of 0.267 is not a
description of the method's quality; it is 19 dry chips dragging down 18 good ones.

This is D10 quantified. It also relocates the problem. The baseline does not need a
better threshold — the threshold is fine where there is something to threshold. It
needs a **gate** that answers "is there any flood in this scene at all?", and
abstains when the answer is no. D10 established that Otsu's own goodness-of-fit
cannot supply that gate.

**Consequences.**

1. This is the clearest statement so far of what the learned model must contribute:
   not a sharper boundary on flooded scenes, but the ability to say *no water here*.
   A U-Net trained with dry chips in the training set learns that directly, which
   Otsu structurally cannot.
2. Any headline accuracy figure must be stated **stratified**. A single mean over a
   mixed set is dominated by the proportion of dry chips in the sample, so it says
   more about the sample than about the method — and it moves whenever the sample
   does, which is how a benchmark number becomes unfalsifiable.
3. Regional spread is now visible and should be watched rather than averaged away:
   Mekong 0.563, India 0.319, Somalia 0.047 (n=5). Whether Somalia is genuinely
   harder or simply drier is not yet established.

---

### D14 — The first U-Net does not beat the deterministic baseline

**Result.** Trained 60 epochs on 41 chips (Ghana, Mekong, Nigeria, Pakistan,
Paraguay), evaluated on 19 chips from two regions never seen in training (India,
Somalia):

| | IoU | F1 |
|---|---|---|
| deterministic baseline | **0.242** | 0.307 |
| U-Net, 486k parameters | 0.234 | 0.310 |

Stratified, which is where the finding is:

| water in chip | baseline | U-Net |
|---|---|---|
| < 1% | 0.003 | **0.003** |
| 1–10% | 0.147 | 0.124 |
| 10–30% | 0.324 | **0.354** |
| > 30% | 0.810 | 0.791 |

**The model did not learn the one thing it was added to learn.** D13 identified the
capability gap as the ability to output *nothing* on a dry scene. The `<1%` row is
unchanged. The model over-predicts water on dry ground exactly as Otsu does.

**It is not a calibration problem.** The decision threshold was swept, in case the
model had learned something that 0.5 was hiding:

| threshold | IoU | precision | recall | IoU `<1%` |
|---|---|---|---|---|
| 0.3 | 0.139 | 0.139 | 0.995 | 0.002 |
| 0.5 | **0.234** | 0.257 | 0.778 | 0.003 |
| 0.7 | 0.174 | 0.554 | 0.202 | 0.005 |
| 0.9 | 0.058 | 0.520 | 0.063 | 0.004 |

0.5 is already near-optimal, and no threshold rescues the dry chips. Raising it
trades recall away without buying precision where it is needed. The model has not
learned a signal that a better cut point would expose.

**Diagnosis: not enough data, and the architecture is not the suspect.** Two
supporting observations. The one bucket where the model *does* beat the baseline is
10–30% water (+0.030), the regime with enough positive pixels to learn a boundary
from and enough negatives to constrain it. And validation IoU plateaued from epoch
53 — the model converged; it did not run out of time.

41 training chips is the binding constraint. It is also self-inflicted:
`fetch_sen1floods11.py` reads `flood_valid_data.csv`, so every chip used here comes
from Sen1Floods11's *validation* split. The hand-labelled train split is a separate,
larger CSV that has not been touched, and there is a much larger weakly-labelled
set beyond it. Fetching those is the obvious next move and costs nothing but disk.

**What is reportable today.** The deterministic baseline, at IoU 0.242 on held-out
regions, is the current best method — and the harness said so rather than hiding
it, which is the property that makes the number worth quoting at all. A learned
model that ties its baseline on 41 chips is a normal result, not a failed project;
what would have been a failure is reporting 0.234 as an improvement.

---

### D15 — With enough data the U-Net beats the baseline, and wins where predicted

**Result.** 308 training chips across eight regions, 20 epochs. Held out India and
Somalia — 92 chips, never seen in training.

| | IoU | F1 |
|---|---|---|
| deterministic baseline | 0.189 | 0.262 |
| U-Net, 486k parameters | **0.261** | **0.361** |
| difference | **+0.072** | +0.099 |

A 38% relative improvement in IoU. This supersedes D14, which measured the same
comparison on 41 training chips and found a tie; the diagnosis there — that data
volume was the binding constraint, not the architecture — holds.

**Where the improvement comes from is the whole point:**

| water in chip | baseline | U-Net | |
|---|---|---|---|
| < 1% | 0.003 | **0.016** | 5× |
| 1–10% | 0.095 | **0.246** | 2.6× |
| 10–30% | 0.293 | **0.321** | |
| > 30% | **0.748** | 0.714 | baseline still ahead |

D13 identified the capability gap precisely: Otsu always splits a histogram, so it
invents a flood on dry ground, and the fix had to be a model that can output
nothing. The gain is concentrated in exactly the two driest buckets and the model
is *worse* on the wettest one, where thresholding was already close to adequate.
That is the predicted shape, and it is a stronger result than the headline number:
the two methods fail differently, which is what makes their agreement a usable
confidence signal (D5, `ConfidenceBasis.MODEL_AGREEMENT`).

**On the baseline number moving.** It reads 0.189 here against 0.242 in D14. The
methods are unchanged; the validation set is not. It went from 19 chips to 92, with
many more Indian scenes, and it is harder. This is the concrete case for what D13
insisted on — a single mean says as much about the sample as the method, and only
numbers measured on the same split may be compared. The pairing in the table above
is valid because both were scored on the same 92 chips in the same run.

**Still not solved.** 0.016 on the driest bucket is five times better than 0.003
and still close to useless in absolute terms. The model has begun to learn
restraint on dry scenes rather than acquired it. That is the next target, and the
honest framing for any external claim.

**Reproduce:**

    python3 fetch_sen1floods11.py --split all --count 400
    PYTHONPATH="$PWD" python ml/scripts/train_unet.py --epochs 20 --val-every 4

---

### D16 — A gate with an absurd escape hatch is a gate that gets bypassed

The P3-15 staleness gate shipped with one documented remedy for a false positive:
regenerate the report, which means a 533 MB download and a full re-score. Six days
later a `stamp_report.py` step ran in CI immediately before the gate, writing the
current fingerprint into the report so the comparison compared a value against
itself. The gate could no longer fail at all.

Measured rather than argued. Inverting the water polarity in `ml/pipeline/baseline.py`
— `np.less` to `np.greater`, one word, which turns every water measurement into a
measurement of everything that is not water — produced this:

```
Stamped reports/evaluation.md: 3d9e162ee74c4ba7 -> e4ff223d71ff72cb
reports/evaluation.md is current (fingerprint e4ff223d71ff72cb)
exit 0
```

The report went on publishing IoU 0.259 as a description of that code.

**The bypass was a rational response to a badly designed gate.** It fired on a
`@` → `*` operator swap that returns identical values, and the only sanctioned
answer was the 533 MB round trip. Reverting alone would have recreated the
pressure and, in time, the bypass.

**Decision.** The escape hatch stays and becomes attributable. `waive_report.py`
requires `--by` and `--reason`, never runs in CI, and appends a row to
`reports/evaluation-waivers.md` naming the fingerprint, the modules that changed,
the person and the reason. The gate accepts a waived fingerprint and prints the
row loudly rather than passing quietly. A waiver is pinned to one fingerprint, so
it expires the moment anything else moves — otherwise one docstring waiver carries
every later change in behind it.

Two supporting changes came out of the same analysis. A stale report now names
*which* modules moved, because "something changed" is what sent someone looking
for a bypass. And the gate no longer imports the report generator — it needed
rasterio, the training dataset and the learned pipeline to answer a question about
file hashes, and a gate that can fail from an unrelated import is a gate that gets
switched off.

**The test for this is on `ci.yml`, not on Python.** `check_report_fresh.py` was
correct throughout; it was handed a rewritten report a second earlier. A test that
only exercised the Python would have passed against the broken CI.

### D17 — One contract module, and the validators are what make it one

`packages/contracts/ml.py` (P1) and `ml/contracts/` (P3) both existed, and the
canonical one had the strict *configuration* — `frozen=True`, `extra="forbid"`,
`revalidate_instances="always"` — and none of the strict *behaviour*. The
validators had not survived transcription. Measured against that file before the
fix: hectares in EPSG:4326 constructed, a negative area constructed, and a
`NOT_CALIBRATED` confidence carrying 0.9 constructed.

Each of those is the failure mode D1 and D2 exist to prevent — a wrong number
arriving with full provenance attached, which makes it read as *more* credible,
not less. A file that careful-looking which validates nothing is worse than one
that never claimed to, because reviewers stop reading it.

**Decision.** `ml/contracts/` is deleted; `packages/contracts` is the only
contract package. Restoring the validators there completes what that module's own
docstring already promised rather than overriding P1's intent. `crs_policy` moved
to `packages/contracts/` because `Measurement` enforces it, so it has to be
importable without `packages/` depending on `ml/` — and it keeps its deliberate
zero dependencies, since `packages/geo` would drag in rasterio.

No field, type, requiredness or enum member changed. That was checked by
snapshotting every model's `model_fields` before and after and diffing, not by
reading — the whole reason this decision exists is that reading a contract file
is not sufficient to know what it enforces.

**What stops it recurring** is 35 tests in
`packages/contracts/tests/test_validators_present.py`, and two rules they follow
that were learned while writing them:

- Every test asserts on the *error message*, not merely that a `ValidationError`
  was raised. The first draft passed seven of seven while testing nothing — the
  probe objects were missing required fields, pydantic raised for that reason, and
  `except ValidationError` swallowed it as a pass.
- Every builder is exercised unmodified at import time, so a broken happy path
  fails at collection instead of turning the whole module green for the wrong
  reason.

Removing the three validators that were originally lost fails 12 of the 35.

`PHYSICAL_UNITS` membership is pinned by a test rather than by adding
`packages/contracts/ml.py` to `FINGERPRINTED`. Its validators only ever refuse;
none can change a number. Fingerprinting it would make every docstring edit to
P1's file cost a 400-chip regeneration — which is precisely the pressure D16 is
about.

### D18 — Report pooled IoU and per-chip mean together, and refuse accuracy outright

The report quoted mean-of-per-chip IoU alone: 0.259 held out. Pooled over every
scorable pixel — the aggregation the Sen1Floods11 literature uses — the same model
on the same chips scores **0.421 IoU / 0.593 F1**. Nothing changed but the
arithmetic of aggregation.

Neither is wrong and neither is sufficient. Averaging per-chip IoU gives a
512×512 tile holding nine water pixels the same vote as a half-flooded one, and
most of this benchmark is nearly dry, so the mean is dominated by chips where one
misplaced pixel swings the score. That is the right question for "how does this do
on a typical chip" and the wrong one for "how much water did it find in this
region" — and it is not comparable to any published number.

**Decision.** Both, in the same table, always. Quoting either alone without naming
the aggregation is how two people end up arguing about the same model, and it is
also how a headline figure gets quietly picked for being the flattering one.

**Accuracy is printed only to be refused.** Water is 10.8% of scorable pixels on
the held-out split, so a model predicting no water anywhere scores **89.2%
accuracy and 0.000 IoU**. The U-Net reaches 90.8% — 1.6 points above doing
nothing. Any goal of the form "N% accuracy" on this task is met by a model that
does nothing, so the report states the floor next to the figure rather than
omitting accuracy and leaving someone to compute a flattering version of it later.

`SegmentationMetrics.accuracy` and `.prevalence` exist for that paragraph and no
other purpose; the docstrings say so.

### D19 — Weak supervision at 13x the data did not help. Reported, not buried.

The hand-labelled set is 446 chips and this project holds 400, so the only place
more data existed was Sen1Floods11's 4,384 weakly-labelled chips -- labels derived
from Sentinel-2 spectral indices rather than drawn by a person. D14/D15 had
established data volume as the binding constraint (41 chips tied the baseline, 308
beat it), so this was the obvious lever. It was pulled, and it did not work.

Four models and the baseline, scored in one process against the same 92 held-out
chips on the same reprojected grid:

| method | pooled IoU | pooled F1 | chip IoU | chip F1 |
|---|---|---|---|---|
| deterministic baseline | 0.204 | 0.339 | 0.209 | 0.289 |
| flood-unet (incumbent, 2ch, 20 epochs) | 0.421 | 0.593 | 0.259 | 0.359 |
| **hand-only-v2** (3ch + JRC prior, 30 epochs) | **0.435** | **0.606** | 0.254 | 0.348 |
| flood-unet-v2 (weak pretrain -> hand fine-tune) | 0.398 | 0.569 | 0.261 | 0.356 |
| pretrain (weak labels only) | 0.407 | 0.579 | 0.245 | 0.337 |

Twelve epochs over 4,096 chips -- 3,788 of them weak -- then thirty fine-tuning
epochs on the 308 hand chips, produces 0.398 pooled. That is **worse than the
incumbent and worse than the same architecture trained on hand labels alone.**

**The training curve says why.** Training loss fell to 0.34 against 0.49 for the
hand-only run: the model fitted the weak labels far better than it had ever fitted
the hand ones. Held-out pooled IoU across the same run went 0.448, 0.445, 0.413,
0.435 -- flat to slightly down while the loss kept falling. That is the signature
of learning the *label generator* rather than the phenomenon. The weak labels
encode where a Sentinel-2 spectral index says water is, and the model became good
at predicting that index from SAR; thirty epochs of fine-tuning on 308 chips did
not undo it.

**What this closes.** Volume is no longer the binding constraint, so D14's
diagnosis does not extend indefinitely: more *weakly* labelled data is not the
route past 0.44, and the remaining hand-labelled set is 46 chips. The next lever
is not data.

**The JRC permanent-water prior is unproven.** `hand-only-v2` adds it and is +0.014
pooled over the incumbent, -0.005 on the per-chip mean -- the two aggregations
disagree, the margins are small, and there is no seed-variance estimate, so no
claim is made either way. It is not evidence the prior works; it is evidence it
does not hurt.

**A measurement trap worth recording.** `train_unet.py` scores on the chip's
native grid; `generate_report.py` reprojects to an area-safe CRS first. The
baseline -- identical code in both -- reads 0.186 from training and 0.204 from the
report on the same 92 chips. Every number in this table comes from the report
path. Comparing a training console figure against a committed one is invalid, and
the two were nearly compared before the discrepancy in the baseline gave it away.

**Still open, and deliberately not fixed under deadline:** `ModelRegistry.default()`
ranks on the per-chip mean recorded in metrics.json, which is the native-grid
figure, while this table ranks on reprojected pooled IoU. The two disagree here --
the registry would serve `flood-unet` where the report's winner is `hand-only-v2`.
Both beat the baseline and the gap is 0.014, so the operational cost is small, but
it is the same defect class as D18 and should be closed by recording reprojected
scores at training time.

## Open questions

These do not block this commit. Each blocks something later.

| # | Question | Ask | Blocks |
|---|---|---|---|
| **OPEN-1** | Is the inference API `/api/v1/inference/*` (P3 spec) or `/api/v1/analysis` + `/api/v1/change-detection` + `/api/v1/models` (Master PRD §16)? | P1 | The service skeleton and router (P3-01). P5 generates its client from the gateway's OpenAPI, so a wrong path is discovered only at integration. |
| **OPEN-2** | Does "deterministic fixture fallback is allowed for the SIH demo" still stand, given the project decision to ship no fabricated data? D7 assumes it does not. | P1 + P6 | The whole design of P3-14 and the failure-mode table. The two positions are mutually exclusive. |
| **OPEN-3** | Is cross-modal optical–SAR fusion (P3-06) genuinely required by 20 Sep, or may it be replaced by agreement reporting? | P1 / collective | Two of the nine remaining days. It is P0 with no defined success criterion, and needs cloud-free optical coincident with a flood — the condition that by definition does not hold. |
| **OPEN-4** | Which live imagery provider will P4 use? D4 recommends ASF HyP3. | P4 | The units of every live scene, whether reprojection is needed before measurement, and therefore the preprocessing contract. |

Two further items are answered provisionally and should be confirmed:

- **Dataset split of work.** Train the single-date segmentation model on the
  Sen1Floods11 hand-labelled split (verified conventions, standard benchmark,
  comparable to published baselines); validate the *bi-temporal* path on SenForFlood's
  CEMS-derived subset (1,339 manually checked samples with genuine pre- and
  during-flood SAR, dense over India). Do **not** train on SenForFlood's
  auto-generated 97% — those labels come from VH differencing, which is close to what
  the Otsu baseline does, and training on them would make baseline and model agree for
  the wrong reason, destroying the independence that makes their agreement a valid
  confidence signal.
  Source: SenForFlood, ISPRS Archives XLVIII-M-7-2025.

- **Why a U-Net rather than a geospatial foundation model.** PANGAEA
  (arXiv:2412.04204) found GFMs do not consistently outperform supervised models
  including U-Net, under limited labelled data, across resolutions, sensors and
  regions. Prithvi-EO is additionally an *optical* model, which is a sensor mismatch
  for a chain running on Sentinel-1 precisely because monsoon flooding sits under
  cloud. Foundation models belong in the ablation table as a comparison row, not in
  the analysis path.

---

## Consequences

- Anything downstream that needs a number must go through `Measurement`, and will
  fail loudly if it cannot supply provenance. This is intended friction.
- Preflight refuses unrecognised CRS strings. Expect to widen `is_projected` when
  pyproj arrives rather than to loosen the guard.
- The provider allowlist is closed. Adding a provider is a reviewed change to
  `DEFAULT_ALLOWED_HOSTS`, which is the point — an SSRF control anyone can widen by
  accident is not a control.
- P3 does **not** own most of the security controls the spec's section 8 assigns to
  it. Authentication, RBAC, tenant isolation, secrets/TLS and rate limits are P1's;
  prompt injection and AI tool permissions are P2's (there is no LLM in P3 scope at
  all); dependency and container scanning are P6's. P3 owns input and raster
  validation, the SSRF allowlist, and the model-execution audit trail. That table
  needs correcting in writing before the release checklist is used against this role.
