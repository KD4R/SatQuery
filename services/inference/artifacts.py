"""Where an analysis's output files go (P3 work pack, task 2).

A protocol with three implementations, chosen by configuration in
dependencies.py -- the same pattern as RasterSource, so tests swap it through
``app.dependency_overrides`` instead of monkeypatching.

    S3ArtifactSink     MinIO in docker-compose, S3 in production.
    LocalArtifactSink  A directory. Development and tests.
    (none)             No store configured. The analysis still returns; its refs
                       are empty and a caveat says the outputs were not kept.

Persisting is never allowed to fail the analysis. The area was measured
correctly whether or not the mask could be written; losing the measurement
because the bucket was briefly unreachable would trade a real answer for a
storage hiccup. The failure is logged and carried as a caveat instead.

Keys are ``analyses/<trace_id>/<file>``. The trace id is a fresh uuid4 per
request, so two analyses can never write over each other, and the key is the
same id the caller already has for correlating logs.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

#: A key is a relative path of safe segments. Anything else -- "..", absolute
#: paths, backslashes -- is refused before it reaches a filesystem or a bucket.
_SAFE_KEY = re.compile(r"^(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+$")


class ArtifactWriteError(RuntimeError):
    """The store refused or failed a write. Callers degrade, not fail."""


class ArtifactNotFound(LookupError):
    """No artifact under that key. The route turns this into a 404."""


class ArtifactSink(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str:  # pragma: no cover
        """Store ``data`` under ``key`` and return the ref to put in the Analysis."""
        ...

    def get(self, key: str) -> bytes:  # pragma: no cover
        """Read back what ``put`` stored. Raises ArtifactNotFound if absent."""
        ...


def _checked(key: str) -> str:
    if not _SAFE_KEY.match(key) or ".." in key.split("/"):
        raise ArtifactWriteError(f"refusing unsafe artifact key {key!r}")
    return key


class LocalArtifactSink:
    """Writes under a directory. The ref is the key, relative to that directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()

    def put(self, key: str, data: bytes, content_type: str) -> str:
        target = (self.root / _checked(key)).resolve()
        if self.root not in target.parents:
            raise ArtifactWriteError(f"artifact key {key!r} escapes {self.root}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as error:
            raise ArtifactWriteError(f"could not write {key}: {error}") from error
        return key

    def get(self, key: str) -> bytes:
        target = (self.root / _checked(key)).resolve()
        if self.root not in target.parents or not target.is_file():
            raise ArtifactNotFound(key)
        return target.read_bytes()


class S3ArtifactSink:
    """Writes to an S3-compatible bucket. The ref is ``s3://<bucket>/<key>``.

    Uses the same S3_* variables docker-compose already sets for this service and
    packages/providers already reads, so there is one set of credentials, not two.
    """

    def __init__(self, bucket: str, client: Any) -> None:
        self.bucket = bucket
        self.client = client

    @classmethod
    def from_environment(cls) -> "S3ArtifactSink | None":
        endpoint = os.environ.get("S3_ENDPOINT")
        bucket = os.environ.get("S3_BUCKET")
        if not endpoint or not bucket:
            return None
        import boto3  # noqa: PLC0415 -- only needed when a bucket is configured

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        )
        return cls(bucket, client)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        key = _checked(key)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        except Exception as error:  # noqa: BLE001 -- botocore raises many types
            raise ArtifactWriteError(
                f"could not write s3://{self.bucket}/{key}: {error}"
            ) from error
        return f"s3://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        key = _checked(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as error:  # noqa: BLE001 -- botocore raises many types
            raise ArtifactNotFound(key) from error
        body: bytes = response["Body"].read()
        return body
