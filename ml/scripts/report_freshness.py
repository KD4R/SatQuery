#!/usr/bin/env python3
"""Is `reports/evaluation.md` current? Everything needed to answer that.

Split out of ``generate_report.py`` so that the CI gate can import it without
importing the generator. The generator pulls in rasterio, the training dataset and
the learned pipeline; the gate needs none of that, and a gate that can fail because
an unrelated import broke is a gate that gets switched off.

Nothing here imports anything outside the standard library, deliberately.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

#: Modules whose contents can change a reported number. The fingerprint covers
#: these and nothing else: a docstring fix in an unrelated file should not
#: invalidate a report, and a change to Otsu absolutely should.
FINGERPRINTED = (
    # Moved out of ml/ in the contract convergence (ADR-0007 D17). Fingerprinted
    # because is_area_safe() decides
    # whether an area may be computed at all.
    #
    # packages/contracts/ml.py is deliberately NOT here, despite Measurement being
    # where that policy is enforced. Its validators only ever refuse; none of them
    # can change a number. Listing it would mean every docstring edit to P1's file
    # forces a 400-chip regeneration, and a gate that expensive to satisfy is one
    # that gets bypassed -- which is how this gate was disabled the first time. The
    # invariant that actually matters there (PHYSICAL_UNITS membership, so the
    # area-safety guard keeps firing) is pinned by a test instead, which costs
    # nothing to satisfy and runs on every pull request.
    "packages/contracts/crs_policy.py",
    "ml/geo/area.py",
    "ml/geo/crs.py",
    "ml/sar/units.py",
    "ml/sar/change.py",
    "ml/io/raster.py",
    "ml/io/preflight.py",
    "ml/pipeline/baseline.py",
    "ml/pipeline/postprocess.py",
    "ml/evaluation/segmentation.py",
    "ml/models/unet.py",
    "ml/training/dataset.py",
    "ml/training/splits.py",
)

#: Per-module hashes, written beside the report. Only ever used for diagnostics --
#: the gate's verdict comes from the combined fingerprint in the report itself, so
#: deleting this file weakens the error message and nothing else.
SIDECAR = Path("reports/evaluation-fingerprint.json")


def module_hashes(repo_root: Path) -> dict[str, str]:
    """SHA-256 per fingerprinted module.

    Content, not mtime: a checkout reorders timestamps, and a fingerprint that
    changes on clone is a gate everyone learns to ignore.
    """
    hashes: dict[str, str] = {}
    for relative in FINGERPRINTED:
        path = repo_root / relative
        if not path.is_file():
            raise SystemExit(f"fingerprinted module missing: {relative}")
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return hashes


def code_fingerprint(repo_root: Path) -> str:
    """SHA-256 over the analysis modules, in a fixed order."""
    digest = hashlib.sha256()
    for relative in FINGERPRINTED:
        path = repo_root / relative
        if not path.is_file():
            raise SystemExit(f"fingerprinted module missing: {relative}")
        digest.update(relative.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def write_sidecar(repo_root: Path) -> None:
    path = repo_root / SIDECAR
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprint": code_fingerprint(repo_root), "modules": module_hashes(repo_root)}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def changed_modules(repo_root: Path) -> tuple[str, ...]:
    """Which fingerprinted modules differ from the ones the report was built on.

    This is the question a stale-report failure should answer and originally did
    not. "Something changed" sends people looking; "ml/io/raster.py changed" lets
    them decide in one read whether a number could have moved.

    Empty when the sidecar is absent -- the caller must not read that as "nothing
    changed", only as "cannot say".
    """
    path = repo_root / SIDECAR
    if not path.is_file():
        return ()
    try:
        recorded = json.loads(path.read_text())["modules"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return ()
    current = module_hashes(repo_root)
    return tuple(
        relative for relative in FINGERPRINTED if recorded.get(relative) != current.get(relative)
    )


#: The report itself. The fingerprint recorded in it is the gate's source of truth.
REPORT = Path("reports/evaluation.md")

#: Human waivers. A fingerprint listed here is accepted by the gate because a named
#: person asserted the change could not move a number. See ml/scripts/waive_report.py.
WAIVERS = Path("reports/evaluation-waivers.md")

_FINGERPRINT_ROW = re.compile(r"^\|\s*code fingerprint\s*\|\s*`([0-9a-f]+)`\s*\|", re.M)
_WAIVER_ROW = re.compile(r"^\|\s*`([0-9a-f]+)`\s*\|(.*)\|\s*$", re.M)


def read_recorded_fingerprint(repo_root: Path) -> str | None:
    """The fingerprint the report says it was generated from, or None."""
    path = repo_root / REPORT
    if not path.is_file():
        return None
    match = _FINGERPRINT_ROW.search(path.read_text())
    return match.group(1) if match else None


def read_waivers(repo_root: Path) -> dict[str, str]:
    """Waived fingerprint -> the rest of its row, for printing back at the reader.

    Parsed rather than trusted blindly: a waiver only ever *widens* what the gate
    accepts, so a malformed file must fail closed. An unparseable row is simply not
    a waiver, and the gate then fails as if it were absent.
    """
    path = repo_root / WAIVERS
    if not path.is_file():
        return {}
    waivers: dict[str, str] = {}
    for match in _WAIVER_ROW.finditer(path.read_text()):
        waivers[match.group(1)] = match.group(2).strip()
    return waivers
