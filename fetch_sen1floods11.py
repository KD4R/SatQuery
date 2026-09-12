#!/usr/bin/env python3
"""
fetch_sen1floods11.py -- download a working subset of Sen1Floods11 hand-labelled chips.

WHY YOU HAVE TO RUN THIS YOURSELF
---------------------------------
Neither sandbox available to Claude can reach `storage.googleapis.com`: both the
cloud container and the local Linux VM route through an egress proxy that returns
403 `blocked-by-allowlist` for that host. That is a restriction on the sandboxes,
not on the dataset -- Sen1Floods11 is public, free and needs no credentials.

So: run this in **your own macOS Terminal**, not through Claude. Your Terminal has
unrestricted internet; the sandbox does not.

    cd ~/Downloads/SatQuery-ML
    source .venv/bin/activate
    python3 fetch_sen1floods11.py --count 12

Once the files are on disk Claude can read them through the connected folder.

WHAT IT DOWNLOADS
-----------------
For each chip in the hand-labelled validation split, up to four co-registered
512x512 GeoTIFFs:

    S1Hand           the Sentinel-1 scene      2 bands, float32, VH then VV, DECIBELS
    LabelHand        hand-drawn ground truth   int16,  -1 no-data / 0 land / 1 water
    JRCWaterHand     JRC permanent water       for the permanent-water subtraction
    S1OtsuLabelHand  the dataset authors' own Otsu baseline

That last one matters more than it looks: it lets the deterministic baseline in
`ml/` be scored against a published Otsu implementation on identical input, rather
than only against ground truth. If ours disagrees with theirs by a lot, ours is
probably wrong.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
No fallback, no synthetic substitute, no partial success. If a file is missing or
truncated it is reported and the run exits non-zero. A half-downloaded dataset that
silently scores well is the exact failure this project is built to avoid.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

#: A chip stem is a region name and a numeric id, e.g. ``India_1050276``. Anchored
#: and character-restricted so that a value read from the remote split index cannot
#: contain a path separator, a drive letter or a ``..`` component.
#:
#: The index is fetched over the network, so its contents are untrusted input even
#: though the host is reputable. Without this, a compromised or malformed index
#: could steer ``write_bytes`` anywhere the user running the script can write --
#: the destination directory is joined with the value, and ``Path("a") / "/etc/x"``
#: silently discards the "a".
_SAFE_STEM = re.compile(r"^[A-Za-z][A-Za-z0-9]*_[0-9]+$")

BUCKET = "https://storage.googleapis.com/sen1floods11"

# Layout per the official repository, github.com/cloudtostreet/Sen1Floods11.
# Verified structurally, not fetched -- if a path 404s the script says so loudly
# rather than skipping, because a silently-missing layer is how a benchmark ends up
# scoring against three-quarters of its own data.
SPLIT_CSV = f"{BUCKET}/v1.1/splits/flood_handlabeled/flood_valid_data.csv"
HAND = f"{BUCKET}/v1.1/data/flood_events/HandLabeled"

# suffix in the split CSV -> (subdirectory, required?)
LAYERS: dict[str, tuple[str, bool]] = {
    "S1Hand": ("S1Hand", True),
    "LabelHand": ("LabelHand", True),
    "JRCWaterHand": ("JRCWaterHand", False),
    "S1OtsuLabelHand": ("S1OtsuLabelHand", False),
}

TIMEOUT = 120


def _is_tiff_header(head: bytes) -> bool:
    """A GeoTIFF starts with TIFF magic: ``II*\0`` little-endian or ``MM\0*`` big.

    Checked because a proxy or an error page returns HTTP 200 with HTML in the
    body, and rasterio's failure three steps later is far harder to diagnose than
    a refusal here.
    """
    return head in (b"II\x2a\x00", b"MM\x00\x2a", b"II\x2b\x00", b"MM\x00\x2b")


def _looks_like_a_tiff(path: Path) -> bool:
    """Whether an existing file is worth trusting as a cached download.

    Non-empty was the original test, and it accepts a file left behind by an
    interrupted write: the TIFF header lands in the first block, so a truncated
    file still passes a size check and still opens far enough to look real. The
    run then reports every layer complete while the benchmark reads short.

    Truncation is now prevented rather than detected -- see ``_write_atomically``
    -- so this is the check for files written before that, or by something else.
    """
    try:
        if path.stat().st_size < 1024:
            return False
        with path.open("rb") as handle:
            return _is_tiff_header(handle.read(4))
    except OSError:
        return False


def _write_atomically(path: Path, body: bytes) -> None:
    """Write to a temporary file in the same directory, then rename into place.

    ``rename`` within one filesystem is atomic, so the destination path only ever
    holds a complete file. Interrupt the script mid-download and the partial bytes
    are discarded with the temporary file rather than being cached as a valid chip.
    """
    handle, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".part")
    try:
        with os.fdopen(handle, "wb") as sink:
            sink.write(body)
            sink.flush()
            os.fsync(sink.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "satquery-ml/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def read_split(limit: int) -> list[str]:
    """Return chip stems, e.g. 'India_294934', from the validation split CSV."""
    try:
        raw = fetch(SPLIT_CSV).decode("utf-8")
    except urllib.error.HTTPError as exc:
        sys.exit(
            f"Could not read the split index ({exc.code}) at:\n  {SPLIT_CSV}\n\n"
            "If this is a 403 you are behind a proxy that blocks storage.googleapis.com.\n"
            "If it is a 404 the dataset layout has moved -- check\n"
            "  https://github.com/cloudtostreet/Sen1Floods11"
        )

    stems: list[str] = []
    for row in csv.reader(io.StringIO(raw)):
        if not row or not row[0].strip():
            continue
        # Rows look like: Bolivia_103757_S1Hand.tif,Bolivia_103757_LabelHand.tif
        stem = row[0].strip().replace("_S1Hand.tif", "").replace(".tif", "")
        if not _SAFE_STEM.match(stem):
            sys.exit(
                f"Refusing to use chip name {stem!r} from the remote split index: "
                "it is not a plain <Region>_<id> token. This value becomes part of "
                "a filesystem path, so anything unexpected is treated as hostile "
                "rather than sanitised."
            )
        stems.append(stem)
        if len(stems) >= limit:
            break

    if not stems:
        sys.exit(f"The split index parsed to zero chips. First 200 bytes:\n{raw[:200]!r}")
    return stems


def download_chip(stem: str, dest: Path) -> tuple[int, list[str]]:
    """Download every layer for one chip. Returns (bytes written, missing required)."""
    written = 0
    missing_required: list[str] = []

    for suffix, (subdir, required) in LAYERS.items():
        name = f"{stem}_{suffix}.tif"
        out = dest / subdir / name
        out.parent.mkdir(parents=True, exist_ok=True)

        if out.exists() and _looks_like_a_tiff(out):
            print(f"    {subdir:<16} cached")
            continue

        url = f"{HAND}/{subdir}/{name}"
        try:
            body = fetch(url)
        except urllib.error.HTTPError as exc:
            note = "MISSING (required)" if required else "absent (optional)"
            print(f"    {subdir:<16} {note} -- HTTP {exc.code}")
            if required:
                missing_required.append(f"{stem}/{suffix}")
            continue

        if not _is_tiff_header(body[:4]):
            print(f"    {subdir:<16} NOT A TIFF -- got {body[:40]!r}")
            if required:
                missing_required.append(f"{stem}/{suffix}")
            continue

        _write_atomically(out, body)
        written += len(body)
        print(f"    {subdir:<16} {len(body) / 1024:>8.0f} KiB")

    return written, missing_required


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=12, help="chips to fetch (default 12)")
    ap.add_argument(
        "--dest",
        type=Path,
        default=Path("data/sen1floods11"),
        help="destination directory (default data/sen1floods11)",
    )
    args = ap.parse_args()

    print(f"Reading the hand-labelled validation split from\n  {SPLIT_CSV}\n")
    stems = read_split(args.count)
    print(f"{len(stems)} chips selected.\n")

    total = 0
    all_missing: list[str] = []
    for i, stem in enumerate(stems, 1):
        print(f"[{i}/{len(stems)}] {stem}")
        written, missing = download_chip(stem, args.dest)
        total += written
        all_missing.extend(missing)

    print(f"\n{total / 1_048_576:.1f} MiB written to {args.dest.resolve()}")

    if all_missing:
        print(f"\n{len(all_missing)} REQUIRED layer(s) missing:")
        for m in all_missing:
            print(f"  {m}")
        print("\nExiting non-zero -- do not evaluate against an incomplete set.")
        return 1

    print("\nComplete. Every required layer present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
