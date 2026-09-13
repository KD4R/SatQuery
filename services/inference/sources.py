"""Getting a raster from an href to a local path.

Why this is an injectable dependency and not a function
--------------------------------------------------------
P4 owns provider access and has not yet delivered a fetcher, and the provider
itself is still an open question (issue #14 — Bhoonidhi or ASF HyP3 changes the
units of every scene). Writing an HTTPS fetcher here would mean P3 guessing at
P4's job and shipping a second, weaker implementation of it.

So the router depends on a `RasterSource` protocol. The implementation shipped
today resolves hrefs to files already on disk, which is what the benchmark chips
and the demo need. When P4's fetcher lands it satisfies the same protocol and
drops in without touching the router or its tests.

What this deliberately does not do
-----------------------------------
It does not fetch over the network, so it cannot be tricked into being an SSRF
vector by a caller who supplies a clever URL. The allowlist check still runs first
regardless — defence in depth, and because the check is what the *next*
implementation will need most.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

from ml.io.preflight import PreflightError

#: Root under which local rasters may be read. Everything resolves inside it, and
#: a path escaping it is refused rather than clamped -- a caller asking for
#: ../../etc/passwd has either a bug or bad intent, and neither is served by
#: quietly returning a different file than the one requested.
DATA_ROOT = Path(os.environ.get("SATQUERY_DATA_ROOT", "data")).resolve()


class RasterSource(Protocol):
    """Resolve an href to a readable local path."""

    def resolve(self, href: str) -> Path:  # pragma: no cover - protocol
        ...


class LocalRasterSource:
    """Resolve ``file:`` and bare-path hrefs to files under ``root``.

    Accepts a path relative to the root, or an absolute path that *is* inside the
    root. Anything else is refused.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root).resolve() if root is not None else DATA_ROOT

    def resolve(self, href: str) -> Path:
        parsed = urlparse(href)

        if parsed.scheme in ("", "file"):
            raw = unquote(parsed.path if parsed.scheme == "file" else href)
        else:
            raise PreflightError(
                f"this deployment can only read local rasters, and {href!r} has "
                f"scheme {parsed.scheme!r}. Remote fetching is P4's provider "
                "client (issue #14); when it lands it satisfies the same "
                "RasterSource protocol and this message goes away."
            )

        candidate = Path(raw)
        resolved = (candidate if candidate.is_absolute() else self.root / candidate).resolve()

        # Containment checked after resolve(), so that symlinks and .. segments are
        # already collapsed. Checking the string beforehand is the classic mistake:
        # "data/../../etc/passwd" starts with the root right up until it does not.
        if not resolved.is_relative_to(self.root):
            raise PreflightError(f"refusing to read {href!r}: it resolves outside {self.root}")

        if not resolved.is_file():
            raise PreflightError(f"no raster at {href!r} (looked in {resolved})")

        return resolved
