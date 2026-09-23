"""Fetch a model's weights by checksum and put them where the registry looks.

    PYTHONPATH="$PWD" python ml/scripts/fetch_model.py hand-only-v2
    PYTHONPATH="$PWD" python ml/scripts/fetch_model.py hand-only-v2 --from artifacts/

Reads ``infrastructure/models/<name>/manifest.json`` and places ``best.pt``,
``metrics.json`` and ``calibration.json`` under ``$SATQUERY_MODEL_ROOT/<name>/``.
Every file is checked against the manifest's sha256 *before* it is moved into
place: a download that is truncated, corrupted or swapped never reaches the
directory the registry reads. Written to a temporary name and renamed, so a
half-finished fetch cannot leave a partial checkpoint that looks complete.

Two sources:

  --from DIR   copy from a local directory (a teammate's artifacts/, a USB stick)
  (default)    download from the manifest's s3:// URI using the S3_* variables
               docker-compose already sets for the inference service

This is the missing half of infrastructure/models/README.md's promise that weights
are "distributed through the registry and fetched by checksum". The registry
half -- refusing a mismatched file at load -- is in services/inference/registry.py.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


class FetchError(RuntimeError):
    pass


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_files(manifest: dict) -> dict[str, str]:
    """Filename -> sha256 for everything that must land beside the checkpoint."""
    artifact = manifest["artifact"]
    files = {artifact["file"]: artifact["sha256"]}
    files.update(manifest.get("sidecars", {}))
    return files


def _download_s3(uri: str, filename: str, destination: Path) -> None:
    import boto3  # noqa: PLC0415 -- only needed for the S3 path

    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        raise FetchError(f"expected an s3:// URI, got {uri!r}")
    prefix = parsed.path.lstrip("/").rsplit("/", 1)[0]
    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )
    client.download_file(parsed.netloc, f"{prefix}/{filename}", str(destination))


def fetch(
    name: str,
    *,
    manifest_root: Path,
    model_root: Path,
    source_dir: Path | None = None,
) -> Path:
    manifest_path = manifest_root / name / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise FetchError(f"cannot read {manifest_path}: {error}") from error

    target = model_root / name
    target.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=target) as staging:
        staged: list[tuple[Path, Path]] = []
        for filename, want in expected_files(manifest).items():
            temp = Path(staging) / filename
            if source_dir is not None:
                origin = source_dir / name / filename
                if not origin.is_file():
                    raise FetchError(f"{origin} does not exist")
                shutil.copyfile(origin, temp)
            else:
                _download_s3(manifest["artifact"]["uri"], filename, temp)

            got = sha256_file(temp)
            if got != want:
                raise FetchError(
                    f"{filename}: sha256 {got[:16]}... does not match the manifest's "
                    f"{want[:16]}...; refusing to install it"
                )
            staged.append((temp, target / filename))

        # Everything verified; only now does anything touch the live directory.
        for temp, final in staged:
            os.replace(temp, final)

    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    parser.add_argument("--from", dest="source_dir", type=Path, default=None)
    parser.add_argument("--manifests", type=Path, default=Path("infrastructure/models"))
    parser.add_argument(
        "--to", type=Path, default=Path(os.environ.get("SATQUERY_MODEL_ROOT", "artifacts"))
    )
    args = parser.parse_args(argv)
    try:
        where = fetch(
            args.name,
            manifest_root=args.manifests,
            model_root=args.to,
            source_dir=args.source_dir,
        )
    except FetchError as error:
        print(f"fetch failed: {error}", file=sys.stderr)
        return 1
    print(f"{args.name}: verified and installed at {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
