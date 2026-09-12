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
src/ml/
├── contracts/     Frozen pydantic models. The spine — everything else speaks these.
│   ├── base.py           Strict base: extra=forbid, frozen, revalidated
│   ├── scene.py          SceneRef, RasterSpec, ScenePair (orbit-matching rule)
│   ├── measurement.py    Measurement + the projected-CRS guard
│   ├── confidence.py     Confidence with a declared basis, or None
│   └── outcome.py        Analysis | Abstention, AbstentionReason
├── geo/
│   ├── crs.py            UTM zone arithmetic, projected-CRS guard
│   └── area.py           area_hectares — the ONLY user-visible area
├── sar/
│   ├── units.py          Scale conversion; the double-dB trap closed
│   └── change.py         Log-ratio, Otsu threshold, water mask
├── metrics/
│   └── segmentation.py   IoU/F1/precision/recall with no-data exclusion
└── preflight/
    └── raster.py         Input validation + provider SSRF allowlist
```

---

## Getting started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

pytest -q          # 92 tests, no network, no GPU, under a second
ruff check .
ruff format --check .
mypy
```

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
| **Band-order mismatch** | Sen1Floods11 files are VH-then-VV; models here consume VV-then-VH. Mismatching normalises each channel with the other's statistics | `RasterSpec.band_order` is explicit; preflight compares source against model order and refuses |
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
[`docs/adr/ADR-ML-001-foundation.md`](docs/adr/ADR-ML-001-foundation.md), including the
API path conflict, whether cross-modal fusion stays P0, and whether the deterministic
fixture fallback authorised in the P3 spec still stands. None of them block this
commit; all of them block something.
