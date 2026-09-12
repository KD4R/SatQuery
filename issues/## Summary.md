## Summary

`.importlinter` on `GeoSpatial_Feature` declares:

```ini
root_package = satquery
```

There is no `satquery` package. The repository's importable top level is
`services/`, `packages/`, `ml/` and `apps/`, resolved by the root `conftest.py`
adding the repo root to `sys.path`.

As written, import-linter errors out rather than enforcing anything — so the
architectural boundaries *look* protected and are not. That is worse than having
no config at all, because the file's presence discourages anyone from checking.

Separately, `ml` is absent from the `layers` contract, so once `MachL` lands the
ML subsystem is entirely unconstrained.

And it is not invoked by `.github/workflows/ci.yml` at all, so even a correct
config would never run.

## Acceptance Criteria

- [ ] `root_packages` lists the four real top-level packages
- [ ] `ml` appears in the layers contract
- [ ] `lint-imports` runs in CI and fails the build on a violation
- [ ] A deliberately illegal import is confirmed to fail the check (test the
      linter, not just the config)

## Technical Notes

```ini
[importlinter]
root_packages =
    apps
    services
    packages
    ml

[importlinter:contract:layers]
name = Layered architecture
type = layers
layers = apps
         services
         ml
         packages
```

`ml` sits between `services` and `packages`: it may import shared packages, and
services may import it, but it must not reach back up into a service. That is the
boundary P3 is currently maintaining by hand, and it would be better maintained by
the build.

Note `root_packages` (plural) rather than `root_package` — the singular form takes
one name only, which is what produced the current state.
## Summary

`packages/geo/crs.py` reprojects every raster to a single constant:

```python
DEFAULT_PROJECTED_CRS = "EPSG:32643"   # UTM zone 43N
```

The comment above it is right that EPSG:4326 must never be used for area. But a
single UTM zone is not correct for all of India either. UTM zones are 6° of
longitude wide and distortion grows with distance from the zone's central
meridian:

| AOI | Correct zone | Under 43N |
|---|---|---|
| Kuttanad, Kerala (76.4 E) | 43N | correct |
| Guntur, Andhra Pradesh (80.4 E) | **44N** | one zone off |
| Assam / Brahmaputra (92–95 E) | **46N** | three zones off |

Guntur is the demo scenario in the Master PRD and Assam is the most flood-prone
AOI in the country, so this is not a hypothetical edge case.

The failure mode is a silently wrong hectare figure, not an exception — which
makes it the same class of defect as measuring in degrees, just smaller.

## Acceptance Criteria

- [ ] Target CRS is selected per-AOI from its centroid, not from a constant
- [ ] `EPSG:32643` remains available as an explicit override, not as the default
- [ ] Tests covering Kerala (43N), Guntur (44N), Assam (46N) and a
      southern-hemisphere longitude
- [ ] A single implementation, not one per package

## Technical Notes

P3 already has this, tested against those cases:

```python
from ml.geo.crs import utm_epsg_for
target_crs = utm_epsg_for(lon, lat)     # "EPSG:32644" for Guntur
```

It is arithmetic — `32600 + zone` for the northern hemisphere, `32700 + zone` for
the southern, with the zone from `floor((lon + 180) / 6) + 1` — so it needs no
lookup table and no network.

Two options, P4's call:

- **(a)** `packages/geo/crs.py` imports it from `ml/geo/crs.py`. Wrong direction
  architecturally — a shared package would depend on `ml/` — so not preferred.
- **(b)** Move `utm_epsg_for`, `is_projected` and `assert_projected` into
  `packages/geo/crs.py`; `ml/` imports them from there. **Preferred**, since they
  are general geospatial utilities with nothing ML-specific about them.

P3 keeps the local copy only until (b) lands, then deletes it.

Note the polar caveat: UTM is undefined beyond ±84°, and the P3 implementation
raises rather than returning a nonsense zone. Not relevant for India, relevant if
this is ever reused.
## Summary

`GeoSpatial_Feature` contains a Bhoonidhi client with a token store and Redis
locking, which reads as ISRO-first. The P3 plan recommended ASF HyP3 instead.
Both are defensible; the decision is P4's. But P3 is blocked on the answer,
because it determines the units every live scene arrives in.

**The case for ASF HyP3:** the requester chooses the output scale explicitly —
power, amplitude or **decibel** — which removes the dB-versus-linear ambiguity *by
construction* rather than by assumption. It emits float32 COGs already projected
to UTM, which is the projection area measurement requires, so a reprojection step
and a class of error disappear with it. It uses Copernicus GLO-30, the same DEM
the terrain mask wants.

**The case for Bhoonidhi:** sovereignty. It is an ISRO source for an ISRO
hackathon, the client is already written, and it is a genuinely stronger story in
front of a judging panel.

These are not mutually exclusive — Bhoonidhi primary with HyP3 as fallback is a
reasonable answer, as is the reverse. What P3 cannot do is guess.

## Acceptance Criteria

- [ ] Primary provider confirmed in writing (a comment on this issue is enough)
- [ ] The pixel units that provider delivers are recorded — power, amplitude or
      decibel — with a link to the product spec that says so
- [ ] Whether the delivered product is projected or geographic is recorded
- [ ] If Bhoonidhi: the NRSC credential application is **submitted**, not planned

## Technical Notes

`ml/sar/units.py::ensure_decibel()` takes the *declared* scale as a required
argument and never inspects pixel values to guess, because guessing is sometimes
wrong and a sometimes-wrong silent conversion is worse than no conversion. So the
answer to this issue is literally the value P3 passes in — a no-op if the provider
delivers dB, a real conversion if it delivers power.

**The credential timeline is the actual risk here.** Government credential
issuance runs in weeks. It is the only item on the P3 plan that no amount of
engineering effort accelerates, so if the answer is Bhoonidhi, the application
should go in the day this is decided rather than the day the code is ready.

References:
- ASF HyP3 Sentinel-1 RTC Product Guide —
  https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/
- Recorded as OPEN-4 in `docs/adr/ADR-0007-ml-inference-foundation.md`
## Summary

Two independent allowlists guard asset fetching, and they disagree:

| | `packages/geo/validation.py` (P4) | `ml/preflight/raster.py` (P3) |
|---|---|---|
| Hosts | `planetarycomputer.microsoft.com`, `sentinel-cogs.s3.us-west-2.amazonaws.com`, `*.nrsc.gov.in` | ASF (4 hosts), CDSE (3 hosts), `bhoonidhi-api.nrsc.gov.in` |
| Schemes | **`http`**, `https`, `s3` | `https`, `s3` |

Two policies in one repository means the weaker one is the effective one, because
an attacker picks the path. Two specific concerns with the current P4 version:

**`http` is allowed.** An asset fetched over plaintext can be intercepted or
substituted in transit, and permitting the scheme at all provides a downgrade
target. No provider we use requires it.

**`endswith(".nrsc.gov.in")` is a suffix rule.** It correctly rejects
`evil-nrsc.gov.in`, but it accepts *any* subdomain under `nrsc.gov.in` — so a
single subdomain takeover anywhere in that zone becomes a fetch target. We only
need one host: `bhoonidhi-api.nrsc.gov.in`.

**Redirects are unchecked.** The validation runs on the declared href only. A
permitted host can 302 to a forbidden one, so the fetch layer has to re-check
after every redirect, not just before the first request.

## Acceptance Criteria

- [ ] One allowlist in the repository, in `packages/geo/validation.py`
- [ ] `http` removed from `ALLOWED_PROTOCOLS`
- [ ] `.nrsc.gov.in` suffix match replaced with the exact host
- [ ] The fetch layer re-validates the host after each redirect (or disables
      redirect-following entirely and treats a 3xx as a failure)
- [ ] Tests covering: plaintext rejected, sibling-subdomain rejected,
      lookalike domain rejected, redirect to a forbidden host rejected
- [ ] P3 deletes `validate_href` and `DEFAULT_ALLOWED_HOSTS` from
      `ml/preflight/raster.py` and calls the shared function

## Technical Notes

Proposed merged policy:

```python
ALLOWED_PROTOCOLS = {"https", "s3"}          # http removed

ALLOWED_DOMAINS = {
    # ISRO / Bhoonidhi -- exact host, not a suffix rule
    "bhoonidhi-api.nrsc.gov.in",
    # Microsoft Planetary Computer
    "planetarycomputer.microsoft.com",
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
    # ASF / NASA
    "datapool.asf.alaska.edu",
    "hyp3-api.asf.alaska.edu",
    # Copernicus Data Space Ecosystem
    "zipper.dataspace.copernicus.eu",
    "stac.dataspace.copernicus.eu",
}
```

Whether the ASF and CDSE entries are needed depends on the provider decision in
[P4-22]. Adding a host should stay a reviewed change to this set — an SSRF control
anyone can widen by accident is not a control.

Match on `parsed.hostname`, never on the full netloc, so that
`https://allowed.example@evil.test/` cannot slip through on the userinfo field.
## Summary

`SceneRef` is now defined twice:

| | Definition | Branch |
|---|---|---|
| Canonical | `packages/contracts/data.py` | `GeoSpatial_Feature` |
| Duplicate | `ml/contracts/scene.py` | `MachL` |

Both were written from the same spec — the P4 version's docstring cites "Evidence
contract FIG 4" — so they agree on substance and differ on details. That is the
worst case: the drift is invisible until someone adds a field to one of them and
the other silently keeps validating without it.

Differences today:

| Field | `packages/contracts` | `ml/contracts` |
|---|---|---|
| href field name | `stac_href` | `href` |
| `provider` | `str` | closed enum |
| `pass_direction` | `Optional[str]` | closed enum |
| `cloud_cover` | present | absent |
| mutability | mutable | `frozen=True` |
| unknown fields | silently accepted | `extra="forbid"` |

**`packages/contracts/data.py` is canonical.** Shared contracts belong there, P4
got there first, and P4 is the producer (discovery emits `SceneRef`) while P3 is
only a consumer. The naming in the P4 version is also better — `stac_href` says
what the href is, `cloud_cover` is a field P3 omitted and shouldn't have.

What P3 wants to carry over is the *strictness*, not the field list.

## Acceptance Criteria

- [ ] The strictness changes below are applied to `packages/contracts/data.py`
      (or explicitly rejected with a reason, which is a fine outcome)
- [ ] `SceneRef` is deleted from `ml/contracts/scene.py`; `ml/` imports from
      `packages.contracts.data`
- [ ] `ScenePair` stays in `ml/contracts/` and is adapted to the canonical field
      names
- [ ] No behaviour change to P4's discovery service
- [ ] Full suite green on both branches after the merge

## Technical Notes

### Proposed change to `packages/contracts/data.py`

Keeps P4's fields and naming; adds P3's strictness. Every addition is justified
below.

```python
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class Provider(str, Enum):
    """Closed set, so an unknown provider is a validation error rather than an
    untracked data source appearing in provenance. Add new providers here."""
    BHOONIDHI = "bhoonidhi"
    PLANETARY_COMPUTER = "planetary_computer"
    ASF_HYP3 = "asf_hyp3"
    COPERNICUS_DATASPACE = "copernicus_dataspace"


class PassDirection(str, Enum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"


class SceneRef(BaseModel):
    """Physical reference to an EO asset scene (Evidence contract FIG 4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Provider = Field(..., description="Provider; add new ones to the enum")
    collection: str = Field(..., min_length=1, description="STAC collection ID")
    item_id: str = Field(..., min_length=1, description="STAC item ID")
    acquired_at: datetime = Field(..., description="Acquisition timestamp")
    platform: str = Field(..., min_length=1, description="e.g. EOS-04, Sentinel-1A")
    instrument: str = Field(..., min_length=1, description="Sensor instrument name")
    relative_orbit: Optional[int] = Field(..., description="Critical for SAR comparison")
    pass_direction: Optional[PassDirection] = Field(..., description="Critical for SAR comparison")
    stac_href: str = Field(..., min_length=1, description="Original STAC item href")
    cloud_cover: Optional[float] = Field(..., ge=0, le=100, description="Tile-level cloud %")
```

**`frozen=True`** — `SceneRef` is embedded in `Measurement.derived_from` as
provenance. `Measurement` is frozen, but that does *not* freeze the nested object,
so a caller holding a reference can mutate the provenance after validation. That
defeats the point of attaching it.

**`extra="forbid"`** — a new field arriving from a provider becomes an error
rather than being silently dropped. On a model that parses upstream STAC
responses, silently discarding data we should be handling is exactly the failure
we want to be loud.

**`pass_direction` as an enum** — as `Optional[str]`, `"ASCENDING"`, `"ascending"`
and `"ASC"` all validate. The orbit-match check then compares
`"ASCENDING" != "ascending"` and refuses a good pair, or a normaliser gets bolted
on and two spellings compare equal by accident. A closed enum makes the comparison
mean something.

**`min_length=1`** — `item_id=""` currently validates.

**`Field(...)` instead of `= None` on the optionals** — with a default, a scene
that *forgot* the orbit is indistinguishable from one where the orbit is
deliberately unknown. `ScenePair` refuses to compare scenes with unknown geometry,
so the difference is load-bearing. Callers still pass `None` explicitly; it just
becomes a decision rather than an omission.

**`ge=0, le=100` on `cloud_cover`** — catches a fraction passed where a percentage
is expected, which is otherwise a silent factor-of-100 error.

### Where the orbit rule lives

The docstring correctly marks `relative_orbit` and `pass_direction` as "critical
for SAR comparison", but nothing checks they match *between two scenes*. Comparing
two Sentinel-1 acquisitions from different relative orbits measures the change in
viewing geometry rather than change on the ground, and yields a plausible number
rather than an error.

`ScenePair` in `ml/contracts/scene.py` enforces this and **stays in `ml/`** — it is
ML-domain logic, not a shared wire type. Noted here only so nobody assumes the
constraint lives in `SceneRef`.

### Blocked by

`GeoSpatial_Feature` merging to `main`. `packages/contracts/data.py` does not exist
on `main`, so importing it from `MachL` today breaks that branch's CI immediately.

 
 # #   [ P 4 - 2 2 ]   D e c i s i o n 
 * * B h o o n i d h i * *   i s   t h e   p r i m a r y   p r o v i d e r   d u e   t o   t h e   I S R O   s o v e r e i g n t y   r e q u i r e m e n t ,   d e l i v e r i n g   p r o d u c t s   i n   ' a m p l i t u d e '   b y   d e f a u l t .   A S F   H y P 3   w i l l   s e r v e   a s   t h e   f a l l b a c k   ( p r o v i d i n g   d e c i b e l / p o w e r ) .   T h e   N R S C   c r e d e n t i a l   a p p l i c a t i o n   h a s   b e e n   s u b m i t t e d .  
 