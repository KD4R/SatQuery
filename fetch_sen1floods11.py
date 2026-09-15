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

THE WEAKLY-LABELLED SET (--dataset weak)
----------------------------------------
The hand-labelled set is 446 chips and this project already holds 400 of them, so
"fetch more hand-labelled data" is worth about 46 chips. The 10x is elsewhere:
Sen1Floods11 also ships 4,384 **weakly-labelled** chips, whose labels are derived
automatically rather than drawn by a person.

    S1Weak            the Sentinel-1 scene, same format as S1Hand
    S2IndexLabelWeak  labels derived from Sentinel-2 spectral indices
    S1OtsuLabelWeak   labels derived by Otsu on the VH band

Those labels are noisy by construction, which is the point of the name. They are
training data, never evaluation data -- every reported number in this project comes
from the hand-labelled held-out regions and that does not change. ADR-0007 D14/D15
established data volume as the binding constraint on this model, and this is the
only place more volume exists.

Chip names come from listing the bucket (the GCS JSON API), not from a split CSV.
The hand-labelled splits are published as CSVs; the weak set's are not documented,
and inventing a plausible path would mean a 404 halfway through a long download.
Listing is self-verifying: it either enumerates or it fails immediately.

Size, measured from the hand-labelled chips already on disk rather than guessed: a
scene is 1.57 MB and a label is about 7 KB, so the full weak set is 4,384 chips x 3
layers = 13,155 files and roughly 7 GB, essentially all of it scenes. Use --count to
take it in stages; the script caches, so re-running resumes rather than restarting.

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
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

#: A chip stem is a region name and a numeric id, e.g. ``India_1050276`` or
#: ``Sri-Lanka_152185``. Anchored and character-restricted so that a value read
#: from the remote split index cannot contain a path separator, a drive letter or
#: a ``..`` component.
#:
#: The index is fetched over the network, so its contents are untrusted input even
#: though the host is reputable. Without this, a compromised or malformed index
#: could steer ``write_bytes`` anywhere the user running the script can write --
#: the destination directory is joined with the value, and ``Path("a") / "/etc/x"``
#: silently discards the "a".
#:
#: Hyphens are permitted inside the region name because Sen1Floods11 contains
#: ``Sri-Lanka``; the first version of this pattern did not allow them and refused
#: the whole download. Hyphens are only allowed *between* letter groups, so a stem
#: can be neither ``-x`` nor ``x-``, and no arrangement of letters and hyphens can
#: form ``.``, ``..`` or a path separator.
_SAFE_STEM = re.compile(r"^[A-Za-z]+(?:-[A-Za-z]+)*_[0-9]+$")

BUCKET = "https://storage.googleapis.com/sen1floods11"

# Layout per the official repository, github.com/cloudtostreet/Sen1Floods11.
# Verified structurally, not fetched -- if a path 404s the script says so loudly
# rather than skipping, because a silently-missing layer is how a benchmark ends up
# scoring against three-quarters of its own data.
#: Which hand-labelled split to read chip names from.
#:
#: "valid" was the original default and it silently capped the usable dataset: it
#: is Sen1Floods11's own validation split, a few dozen chips, and training on 41 of
#: them is what ADR-0007 D14 identifies as the binding constraint on the first
#: U-Net. "train" is the larger split; "all" concatenates every hand-labelled one.
#:
#: Note these are the DATASET's splits, not this project's. Our train/validation
#: division is by region (ml/training/splits.py) and is applied to whatever is on
#: disk, so pulling more chips here only ever adds data -- it cannot leak a
#: validation chip into training.
SPLIT_CSVS = {
    "train": "flood_train_data.csv",
    "valid": "flood_valid_data.csv",
    "test": "flood_test_data.csv",
}
HAND = f"{BUCKET}/v1.1/data/flood_events/HandLabeled"
WEAK = f"{BUCKET}/v1.1/data/flood_events/WeaklyLabeled"

#: GCS JSON listing endpoint for the same public bucket. Used only for the weak
#: set, which publishes no split index.
LIST_API = "https://storage.googleapis.com/storage/v1/b/sen1floods11/o"

# suffix -> (subdirectory, required?)
HAND_LAYERS: dict[str, tuple[str, bool]] = {
    "S1Hand": ("S1Hand", True),
    "LabelHand": ("LabelHand", True),
    "JRCWaterHand": ("JRCWaterHand", False),
    "S1OtsuLabelHand": ("S1OtsuLabelHand", False),
}

#: Both label layers are optional *individually* and one of them is required
#: jointly -- see ``download_chip``. S2IndexLabelWeak is the better of the two
#: (spectral indices see water directly; Otsu on VH infers it from darkness), but
#: it is absent for chips with no usable Sentinel-2 overpass, and a chip with an
#: Otsu label is still worth training on.
WEAK_LAYERS: dict[str, tuple[str, bool]] = {
    "S1Weak": ("S1Weak", True),
    "S2IndexLabelWeak": ("S2IndexLabelWeak", False),
    "S1OtsuLabelWeak": ("S1OtsuLabelWeak", False),
}

DATASETS = {
    "hand": (HAND, HAND_LAYERS, ("LabelHand",)),
    "weak": (WEAK, WEAK_LAYERS, ("S2IndexLabelWeak", "S1OtsuLabelWeak")),
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


def read_split(limit: int, urls: list[str]) -> list[str]:
    """Return chip stems, e.g. 'India_294934', from the validation split CSV."""
    try:
        raw = "\n".join(fetch(url).decode("utf-8") for url in urls)
    except urllib.error.HTTPError as exc:
        sys.exit(
            f"Could not read a split index ({exc.code}) from:\n  " + "\n  ".join(urls) + "\n\n"
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


def list_weak_stems(limit: int) -> list[str]:
    """Chip stems for the weakly-labelled set, by listing the bucket.

    The hand-labelled splits are published as CSVs; the weak set's are not
    documented anywhere I could verify. Guessing a plausible CSV path would fail as
    a 404 partway through a multi-gigabyte run, so this enumerates the S1Weak
    prefix instead -- which either works on the first call or fails on it.

    Names from a listing are untrusted input exactly as names from a CSV are, and
    go through the same ``_SAFE_STEM`` check: they become filesystem paths.
    """
    stems: list[str] = []
    token: str | None = None
    prefix = "v1.1/data/flood_events/WeaklyLabeled/S1Weak/"

    while len(stems) < limit:
        query = (
            f"?prefix={urllib.parse.quote(prefix)}&maxResults=1000&fields=items/name,nextPageToken"
        )
        if token:
            query += f"&pageToken={urllib.parse.quote(token)}"
        try:
            page = json.loads(fetch(LIST_API + query).decode("utf-8"))
        except urllib.error.HTTPError as exc:
            sys.exit(
                f"Could not list the weakly-labelled set (HTTP {exc.code}) from:\n"
                f"  {LIST_API}{query}\n\n"
                "403 usually means a proxy is blocking storage.googleapis.com -- run "
                "this in your own Terminal, not through Claude.\n"
                "404 means the bucket layout has moved; check\n"
                "  https://github.com/cloudtostreet/Sen1Floods11"
            )

        for item in page.get("items", []):
            name = item["name"].rsplit("/", 1)[-1]
            if not name.endswith("_S1Weak.tif"):
                continue
            stem = name[: -len("_S1Weak.tif")]
            if not _SAFE_STEM.match(stem):
                sys.exit(
                    f"Refusing to use chip name {stem!r} from the bucket listing: it "
                    "is not a plain <Region>_<id> token, and it would become part of "
                    "a filesystem path."
                )
            stems.append(stem)
            if len(stems) >= limit:
                break

        token = page.get("nextPageToken")
        if not token:
            break

    if not stems:
        sys.exit(
            f"The listing of {prefix} returned no S1Weak chips. The layout has "
            "probably moved -- do not fall back to a guess."
        )
    return stems


def download_chip(
    stem: str,
    dest: Path,
    base: str,
    layers: dict[str, tuple[str, bool]],
    label_layers: tuple[str, ...],
) -> tuple[int, list[str]]:
    """Download every layer for one chip. Returns (bytes written, missing required).

    ``label_layers`` names the layers of which **at least one** must arrive. The
    weak set has two label sources and chips that carry only one of them; a chip
    with an Otsu label and no Sentinel-2 label is still trainable, a chip with
    neither is not, and neither layer can be marked required on its own without
    discarding usable data or accepting unusable data.
    """
    written = 0
    missing_required: list[str] = []
    got_a_label = False

    for suffix, (subdir, required) in layers.items():
        name = f"{stem}_{suffix}.tif"
        out = dest / subdir / name
        out.parent.mkdir(parents=True, exist_ok=True)

        if out.exists() and _looks_like_a_tiff(out):
            print(f"    {subdir:<16} cached")
            got_a_label = got_a_label or suffix in label_layers
            continue

        url = f"{base}/{subdir}/{name}"
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
        got_a_label = got_a_label or suffix in label_layers
        print(f"    {subdir:<16} {len(body) / 1024:>8.0f} KiB")

    if label_layers and not got_a_label:
        print(f"    {'labels':<16} NONE of {', '.join(label_layers)} present")
        missing_required.append(f"{stem}/labels")

    return written, missing_required


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--count", type=int, default=12, help="chips to fetch (default 12)")
    ap.add_argument(
        "--split",
        default="all",
        choices=[*SPLIT_CSVS, "all"],
        help="which hand-labelled index to read names from (default all). "
        "The dataset's own splits -- this project divides by region separately.",
    )
    ap.add_argument(
        "--dataset",
        default="hand",
        choices=sorted(DATASETS),
        help="hand (446 chips, human-drawn labels, the evaluation set) or weak "
        "(4,384 chips, automatically derived labels, training only). Default hand.",
    )
    ap.add_argument(
        "--dest",
        type=Path,
        default=Path("data/sen1floods11"),
        help="destination directory (default data/sen1floods11)",
    )
    args = ap.parse_args()

    base, layers, label_layers = DATASETS[args.dataset]

    if args.dataset == "weak":
        print(f"Listing weakly-labelled chips from {LIST_API}\n")
        stems = list_weak_stems(args.count)
        print(
            f"{len(stems)} chips selected. These labels are derived automatically and "
            "are TRAINING DATA ONLY -- every reported score still comes from the "
            "hand-labelled held-out regions.\n"
        )
    else:
        names = list(SPLIT_CSVS.values()) if args.split == "all" else [SPLIT_CSVS[args.split]]
        urls = [f"{BUCKET}/v1.1/splits/flood_handlabeled/{n}" for n in names]
        print("Reading hand-labelled chip names from:")
        for url in urls:
            print(f"  {url}")
        print()
        stems = read_split(args.count, urls)
        print(f"{len(stems)} chips selected.\n")

    total = 0
    all_missing: list[str] = []
    for i, stem in enumerate(stems, 1):
        print(f"[{i}/{len(stems)}] {stem}")
        written, missing = download_chip(stem, args.dest, base, layers, label_layers)
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
