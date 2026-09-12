# ADR-ML-001 — P3 foundation: contracts, dependencies and the decisions behind them

- **Status:** Accepted for the foundation commit; four items remain open and are listed at the end.
- **Date:** 2026-09-11
- **Owner:** P3 (Srushti)
- **Reviewer:** P1 (Siddharth)
- **Supersedes:** nothing. First ADR in this repository.

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
