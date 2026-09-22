"""Write the committed manifest for a trained model (P3 inference work pack, task 1).

    PYTHONPATH="$PWD" python ml/scripts/write_model_manifest.py hand-only-v2

Reads ``artifacts/<name>/{best.pt, metrics.json, calibration.json}`` and writes
``infrastructure/models/<name>/manifest.json``.

Why a manifest and not the weights
----------------------------------
infrastructure/models/README.md sets the rule: weights are not committed, the
manifest is. Reverting a code commit does not revert model weights, so the pin
has to be a tracked file the registry can check against. The weights travel
through object storage and are fetched by checksum (ml/scripts/fetch_model.py).

Before this existed the README promised that "a tampered or truncated download is
detected" and nothing detected it: the registry loaded whatever best.pt was on
disk. The manifest is what makes that promise checkable, and
services/inference/registry.py now refuses a checkpoint whose sha256 does not
match.

Generated, never hand-edited. A hand-typed checksum is a checksum nobody has
verified, which is worse than none because it looks like one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

MANIFEST_VERSION = 1


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(payload: object) -> str:
    """Hash of a JSON value with sorted keys, so formatting cannot change it."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_manifest(model_dir: Path, bucket: str) -> dict[str, object]:
    import torch  # dev-time script; the manifest needs the checkpoint's own facts

    checkpoint = model_dir / "best.pt"
    if not checkpoint.is_file():
        raise SystemExit(f"no checkpoint at {checkpoint}")

    metrics = json.loads((model_dir / "metrics.json").read_text())
    calibration_path = model_dir / "calibration.json"
    calibration = json.loads(calibration_path.read_text()) if calibration_path.is_file() else None

    state = torch.load(checkpoint, weights_only=True, map_location="cpu")
    name = model_dir.name
    digest = sha256_file(checkpoint)

    return {
        "manifest_version": MANIFEST_VERSION,
        "name": name,
        "version": f"e{metrics.get('epochs', '?')}-s{metrics.get('seed', '?')}",
        "artifact": {
            "file": "best.pt",
            "sha256": digest,
            "bytes": checkpoint.stat().st_size,
            # Content-addressed: the key contains the digest, so a new checkpoint
            # can never overwrite the one an old manifest points at.
            "uri": f"s3://{bucket}/models/{name}/{digest}/best.pt",
        },
        # The metrics file supplies the held-out IoU that every analysis quotes,
        # and decides whether the model is selected by default at all. It is data,
        # not code, but an edited one could promote a worse model -- so it is
        # checksummed alongside the weights and fetched from the same prefix.
        "sidecars": {
            f.name: sha256_file(f)
            for f in (model_dir / "metrics.json", model_dir / "calibration.json")
            if f.is_file()
        },
        "architecture": state["architecture"],
        "preprocessing": {
            "bands": ["VV", "VH"],
            "scale": "decibel",
            "normalisation": state["normalisation"],
            "normalisation_sha256": canonical_sha256(state["normalisation"]),
            "uses_permanent_water_prior": metrics.get("uses_permanent_water_prior"),
        },
        "training": {
            "labelling": metrics.get("training_labelling"),
            "train_regions": metrics.get("train_regions"),
            "validation_regions": metrics.get("validation_regions"),
            "epochs_trained": metrics.get("epochs"),
            # best.pt is the epoch with the best held-out score, not the last one.
            # The registry's version string names the run length; this names the
            # weights actually shipped.
            "epoch_selected": state.get("epoch"),
            "seed": metrics.get("seed"),
            "parameters": metrics.get("parameters"),
            "initialised_from": metrics.get("initialised_from"),
        },
        "metrics": {
            # Mean of per-chip IoU on the native grid -- what train_unet.py selects
            # on and what the registry reports. reports/evaluation.md headlines the
            # pooled IoU on the reprojected grid, which is higher. Both are
            # measurements; they aggregate differently (ADR-0007 D18/D19).
            "validation_iou_per_chip_native": metrics.get("model", {}).get("iou"),
            "baseline_iou_per_chip_native": metrics.get("baseline", {}).get("iou"),
            "report": "reports/evaluation.md",
        },
        "calibration": calibration,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="model directory name under --artifacts")
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--out", type=Path, default=Path("infrastructure/models"))
    parser.add_argument("--bucket", default="satquery")
    args = parser.parse_args(argv)

    manifest = build_manifest(args.artifacts / args.name, args.bucket)
    target = args.out / args.name / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    artifact = manifest["artifact"]
    assert isinstance(artifact, dict)
    print(f"wrote {target}")
    print(f"  sha256 {artifact['sha256']}")
    print(f"  upload {args.artifacts / args.name / 'best.pt'} -> {artifact['uri']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
