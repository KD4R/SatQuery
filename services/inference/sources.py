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
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

from ml.io.preflight import PreflightError
from services.inference.validation import validate_href

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


class RemoteRasterSource(LocalRasterSource):
    """Resolve allowlisted live STAC assets into a local cache."""

    def __init__(self, root: Path | None = None) -> None:
        super().__init__(root or Path(tempfile.gettempdir()) / "satquery-assets")
        self.root.mkdir(parents=True, exist_ok=True)

    def _download(self, href: str) -> Path:
        validate_href(href)
        target = self.root / f"{hashlib.sha256(href.encode()).hexdigest()}.tif"
        if target.is_file() and target.stat().st_size > 0:
            return target
        import httpx
        tmp = target.with_suffix(".part")
        try:
            with httpx.stream("GET", href, follow_redirects=True, timeout=120.0) as response:
                response.raise_for_status()
                validate_href(str(response.url))
                with tmp.open("wb") as output:
                    for chunk in response.iter_bytes():
                        output.write(chunk)
            tmp.replace(target)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            raise PreflightError(f"failed to fetch remote raster: {exc}") from exc
        return target

    def resolve(self, href: str) -> Path:
        if urlparse(href).scheme == "https":
            return self._download(href)
        return super().resolve(href)

    def resolve_scene(self, assets: dict[str, str], bbox: list[float] | None = None) -> Path:
        vv = assets.get("vv") or assets.get("VV")
        vh = assets.get("vh") or assets.get("VH")
        if not vv or not vh:
            raise PreflightError("a Sentinel-1 scene requires both VV and VH assets")
        if bbox is not None:
            if len(bbox) != 4 or bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                raise PreflightError("AOI bbox must be [min_lon, min_lat, max_lon, max_lat]")
            return self._crop_remote_pair(vv, vh, bbox)
        vv_path, vh_path = self._download(vv), self._download(vh)
        import rasterio
        key = hashlib.sha256(json.dumps({"vv": vv, "vh": vh}, sort_keys=True).encode()).hexdigest()
        combined = self.root / f"{key}-vv-vh.tif"
        if combined.is_file() and combined.stat().st_size > 0:
            return combined
        with rasterio.open(vv_path) as vv_src, rasterio.open(vh_path) as vh_src:
            if vv_src.count != 1 or vh_src.count != 1:
                raise PreflightError("VV and VH assets must each contain one raster band")
            if (vv_src.width, vv_src.height) != (vh_src.width, vh_src.height):
                raise PreflightError("VV and VH assets do not have matching dimensions")
            profile = vv_src.profile.copy()
            profile.update(count=2, compress="deflate", BIGTIFF="IF_SAFER")
            tmp = combined.with_suffix(".part")
            with rasterio.open(tmp, "w", **profile) as dst:
                dst.write(vv_src.read(1), 1)
                dst.write(vh_src.read(1), 2)
                dst.set_band_description(1, "VV")
                dst.set_band_description(2, "VH")
            tmp.replace(combined)
        return combined

    def _crop_remote_pair(self, vv: str, vh: str, bbox: list[float]) -> Path:
        """Read only the AOI window from remote COGs using HTTP range requests."""
        import rasterio
        from rasterio.windows import from_bounds, transform as window_transform
        from rasterio.warp import transform_bounds
        validate_href(vv)
        validate_href(vh)
        key = hashlib.sha256(json.dumps({"vv": vv, "vh": vh, "bbox": bbox}, sort_keys=True).encode()).hexdigest()
        target = self.root / f"{key}-aoi.tif"
        if target.is_file() and target.stat().st_size > 0:
            return target
        with rasterio.open(vv) as vv_src, rasterio.open(vh) as vh_src:
            source_bbox = transform_bounds(
                "EPSG:4326", vv_src.crs, *bbox, densify_pts=21
            )
            window = from_bounds(*source_bbox, transform=vv_src.transform)
            window = window.round_offsets().round_lengths()
            if window.width < 1 or window.height < 1:
                raise PreflightError("AOI does not overlap the Sentinel-1 raster")
            vv_data = vv_src.read(1, window=window, boundless=True, fill_value=vv_src.nodata)
            vh_data = vh_src.read(1, window=window, boundless=True, fill_value=vh_src.nodata)
            profile = vv_src.profile.copy()
            profile.update(
                width=vv_data.shape[1], height=vv_data.shape[0], count=2,
                transform=window_transform(window, vv_src.transform),
                compress="deflate", BIGTIFF="IF_SAFER",
            )
            tmp = target.with_suffix(".part")
            with rasterio.open(tmp, "w", **profile) as dst:
                dst.write(vv_data, 1)
                dst.write(vh_data, 2)
                dst.set_band_description(1, "VV")
                dst.set_band_description(2, "VH")
            tmp.replace(target)
        return target
