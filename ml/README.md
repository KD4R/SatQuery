# SatQuery ML

**P3 — inference and machine-learning subsystem.** Owner: Srushti (ML / Computer Vision).

Turns analysis-ready satellite rasters into masks, measurements and the evidence
about how well those measurements hold up. It does **not** own how the rasters are
produced (P4, geospatial) or how the answer is narrated (P2, agent).

---

## Two rules everything here obeys

**1. Every user-visible number carries its provenance.**
A number is only expressible as a `Measurement`, and a `Measurement` cannot be
constructed without naming the function that produced it, the code version, the CRS
it was measured in, and at least one scene it came from. There are no defaults on
any of those fields — the shortcut of returning a bare float fails at construction
rather than shipping.

**2. Absence of an answer is a value, not a placeholder.**
Every analysis entry point returns `Analysis | Abstention`. There is no third
option and, in particular, no "empty result with zeroed values". No code path in
this package fabricates a result. When the primary method fails, the legitimate
responses are an abstention with a machine-readable reason, or a fall back to the
deterministic baseline *labelled as such*.

---

## Layout

```
ml/
├── conftest.py           shared synthetic fixtures, visible to every subpackage
├── crs_policy.py         which CRS may be used for what. Depends on nothing.
├── contracts/            frozen pydantic models (the spine)
│   └── tests/
├── geo/                  UTM arithmetic; area_hectares, the only public area
│   └── tests/
├── sar/                  scale conversion, log-ratio, Otsu thresholding
│   └── tests/
├── io/                   read_raster (the one validated entry point), preflight
│   └── tests/
├── pipeline/             Analysis | Abstention paths; the Otsu baseline
│   └── tests/
├── evaluation/           IoU/F1/precision/recall with no-data exclusion
│   └── tests/
└── scripts/              evaluate_baseline.py -- the reproducible accuracy number

services/inference/       the SSRF allowlist: an access-control decision, so it
                          sits at the service boundary rather than in the library
```

Tests are co-located with the code they cover, matching `packages/auth/tests/`
and `services/gateway/tests/`. Layering runs `services -> ml -> packages`; nothing
in `ml/` imports from `services/`.

---

## Getting started

```bash
# From the repository root -- ml/ is part of the monorepo, not a separate package.
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -m unit ml/          # offline, no GPU, under a second
black --check ml/
flake8 ml/
mypy ml/
```

Training the U-Net additionally needs `pip install -r requirements-ml.txt`, and is
run from a shell rather than from CI -- see `ml/scripts/train_unet.py`.

A note on the virtual environment: create it yourself, on the machine you are
working on. `.venv/` is gitignored, and a venv built on one operating system does
not work on another -- the binaries in `numpy`, `rasterio`, `scipy` and `torch` are
platform-specific, so a Linux venv sitting in the working tree looks usable on a
Mac right up until the first import of anything compiled.

Tests are selected by marker (`-m unit`), matching the repository's CI. An
unmarked test is collected by nothing and runs nowhere, so every test module
sets `pytestmark = pytest.mark.unit`.

Runtime dependencies are **NumPy and pydantic only**. That is deliberate: the whole
suite runs offline with no geospatial stack installed, which keeps CI fast and lets
the contracts be validated anywhere. `rasterio` and `pyproj` arrive with the first
module that genuinely reads a GeoTIFF — not before.

---

## The four traps this code is built around

Each produces a *plausible wrong number* rather than an exception, which is why each
has an explicit guard and a test rather than a comment.

| Trap | What goes wrong | Guard |
|---|---|---|
| **Area in degrees** | Hectares computed in EPSG:4326 are wrong by a factor that varies with latitude, and are internally consistent enough to survive review | `Measurement` rejects physical units in a geographic CRS; `pixel_area_m2` refuses to run |
| **Double dB conversion** | Sen1Floods11 chips are *already* in decibels. Converting again corrupts them silently | `ensure_decibel` takes the *declared* scale and converts only when needed — it never inspects values to guess |
| **Band-order mismatch** | Two bands of the same dtype and shape are interchangeable to every tool in the stack, so a swap normalises each channel with the other's statistics | `RasterSpec.band_order` is explicit; preflight compares source against model order and refuses. Measured: Sen1Floods11 v1.1 is **VV(0) then VH(1)**, contradicting some published descriptions — see ADR-0007 D3 |
| **No-data counted as background** | Sen1Floods11 labels `-1` at chip borders. Scoring those as correct background inflates every metric | `confusion()` requires an explicit `ignore_value`, and *raises* if unexpected labels survive — because casting `-1` to bool makes it `True` |

Also pinned: water is **dark** in SAR, so flooding is a *decrease* in backscatter and
the mask selects pixels **below** the threshold. Inverting this yields a mask of
everything that is not flooded — plausible, and entirely wrong.

---

## Status

This is the foundation commit. What exists is the contract layer, the SAR and
measurement primitives the deterministic baseline needs, metrics, and preflight
validation.

**Not yet built:** the service skeleton and model registry (P3-01), the API surface,
the learned model adapter (P3-04), postprocessing (P3-07), the async worker (P3-10),
calibration (P3-11), and the evaluation report generator (P3-15).

**Open decisions that block later work** are recorded in
[`docs/adr/ADR-0007-ml-inference-foundation.md`](../docs/adr/ADR-0007-ml-inference-foundation.md), including the
API path conflict, whether cross-modal fusion stays P0, and whether the deterministic
fixture fallback authorised in the P3 spec still stands. None of them block this
commit; all of them block something.
