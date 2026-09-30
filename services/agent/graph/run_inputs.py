"""
graph/run_inputs.py — Pure helpers that turn a run's inputs into search and
inference parameters: the AOI, the time window, the scene to analyse, and the
redacted public view of a run.

Kept free of I/O so each rule can be unit-tested on its own. None of these
functions invents a value: when an input is missing they say so (``None`` or
an exception) and the caller decides how the run reports it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit


class AOIError(ValueError):
    """The AOI is missing or is a shape the pipeline cannot measure."""


# ── AOI ───────────────────────────────────────────────────────────────────────


def _polygons_of(geojson: Dict[str, Any]) -> List[List[List[List[float]]]]:
    """Return every polygon (as a list of rings) in a GeoJSON object."""
    if not isinstance(geojson, dict):
        raise AOIError("AOI must be a GeoJSON object")
    kind = geojson.get("type")
    if kind == "Polygon":
        return [geojson.get("coordinates") or []]
    if kind == "MultiPolygon":
        return list(geojson.get("coordinates") or [])
    if kind == "Feature":
        return _polygons_of(geojson.get("geometry") or {})
    if kind == "FeatureCollection":
        polygons: List[Any] = []
        for feature in geojson.get("features") or []:
            polygons.extend(_polygons_of(feature))
        return polygons
    raise AOIError(f"AOI type {kind!r} is not supported; draw a Polygon or MultiPolygon.")


def aoi_geometry(aoi: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalise a Polygon / MultiPolygon / Feature / FeatureCollection AOI to one
    GeoJSON geometry (Polygon or MultiPolygon) in WGS84.

    A bare ``{"bbox": [...]}`` is accepted too and becomes its rectangle.
    Raises ``AOIError`` when there is no usable AOI.
    """
    if not aoi:
        raise AOIError(
            "No area of interest was supplied. Draw an AOI on the map before "
            "running a mission; the agent does not guess a location."
        )
    if "type" not in aoi and isinstance(aoi.get("bbox"), (list, tuple)):
        w, s, e, n = _checked_bbox(aoi["bbox"])
        return {
            "type": "Polygon",
            "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
        }
    polygons = [p for p in _polygons_of(aoi) if p and p[0]]
    if not polygons:
        raise AOIError("The AOI contains no polygon coordinates.")
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def _checked_bbox(values: Iterable[float]) -> Tuple[float, float, float, float]:
    vals = [float(v) for v in values]
    if len(vals) != 4:
        raise AOIError("bbox must be [min_lon, min_lat, max_lon, max_lat]")
    w, s, e, n = vals
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise AOIError(f"bbox {vals} is not a valid WGS84 extent")
    return w, s, e, n


def geometry_bbox(geometry: Optional[Dict[str, Any]]) -> Optional[List[float]]:
    """WGS84 bbox of any GeoJSON geometry, or None when it has no coordinates."""
    points: List[Tuple[float, float]] = []

    def walk(value: Any) -> None:
        if (
            isinstance(value, (list, tuple))
            and len(value) >= 2
            and all(isinstance(v, (int, float)) for v in value[:2])
        ):
            points.append((float(value[0]), float(value[1])))
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk((geometry or {}).get("coordinates"))
    if not points:
        return None
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def aoi_bbox(aoi: Optional[Dict[str, Any]]) -> List[float]:
    """The WGS84 bbox of the user's AOI. Raises ``AOIError`` when there is none."""
    bbox = geometry_bbox(aoi_geometry(aoi))
    if bbox is None:
        raise AOIError("The AOI contains no coordinates.")
    return list(_checked_bbox(bbox))


def bbox_area_km2(bbox: List[float]) -> float:
    """Approximate area of a WGS84 bbox (equirectangular; good to ~1% for small AOIs)."""
    import math

    w, s, e, n = bbox
    mid = math.radians((s + n) / 2.0)
    return abs(e - w) * 111.32 * math.cos(mid) * abs(n - s) * 110.57


# ── Time window ───────────────────────────────────────────────────────────────


def _parse_instant(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def requested_window(
    temporal_window: Optional[Dict[str, Any]],
) -> Optional[Tuple[datetime, datetime]]:
    """The caller's explicit search window, or None when they did not give one.

    Accepts ``{start, end}``, ``{start_date, end_date}``, ``{from, to}`` or
    ``{event_date}`` (searched as the 12 days after the event, one Sentinel-1
    repeat cycle). Raises ``ValueError`` for a window that is present but
    unusable, so the caller can report it instead of silently widening.
    """
    if not temporal_window:
        return None
    tw = temporal_window
    start = _parse_instant(tw.get("start") or tw.get("start_date") or tw.get("from"))
    end = _parse_instant(tw.get("end") or tw.get("end_date") or tw.get("to"))
    event = _parse_instant(tw.get("event_date"))
    if start is None and end is None and event is not None:
        start, end = event, event + timedelta(days=12)
    if start is None and end is None:
        raise ValueError("temporal_window was supplied but has no parseable start/end/event_date")
    now = datetime.now(timezone.utc)
    if end is None:
        end = now
    if start is None:
        start = end - timedelta(days=30)
    if start >= end:
        raise ValueError("temporal_window start must be before its end")
    return start, end


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Scene selection ───────────────────────────────────────────────────────────


def _is_sar(obs: Dict[str, Any]) -> bool:
    scene = obs.get("scene") or {}
    collection = str(scene.get("collection") or "").lower()
    instrument = str(scene.get("instrument") or "").lower()
    platform = str(scene.get("platform") or "").lower()
    return "sentinel-1" in collection or "sar" in instrument or "sentinel-1" in platform


def has_dual_pol(obs: Dict[str, Any]) -> bool:
    assets = obs.get("assets") or {}
    return bool((assets.get("vv") or assets.get("VV")) and (assets.get("vh") or assets.get("VH")))


def coverage_fraction(aoi_box: List[float], footprint_box: Optional[List[float]]) -> float:
    """Fraction of the AOI bbox that the scene footprint bbox covers (0..1)."""
    if not footprint_box:
        return 0.0
    w = max(aoi_box[0], footprint_box[0])
    s = max(aoi_box[1], footprint_box[1])
    e = min(aoi_box[2], footprint_box[2])
    n = min(aoi_box[3], footprint_box[3])
    if e <= w or n <= s:
        return 0.0
    aoi_area = (aoi_box[2] - aoi_box[0]) * (aoi_box[3] - aoi_box[1])
    return ((e - w) * (n - s)) / aoi_area if aoi_area > 0 else 0.0


def rank_sar_scenes(
    observations: List[Dict[str, Any]],
    aoi_box: List[float],
    exclude: Iterable[str] = (),
) -> List[Dict[str, Any]]:
    """Sentinel-1 scenes with both VV and VH, best first.

    Best = covers the whole AOI (a partial scene measures only part of it), then
    the most recent acquisition. Scenes in ``exclude`` (already analysed) are
    dropped. Returns an empty list when no scene can be analysed.
    """
    skip = set(exclude)
    usable = [
        o
        for o in observations
        if o.get("observation_id") not in skip and _is_sar(o) and has_dual_pol(o)
    ]

    def key(o: Dict[str, Any]):
        cov = coverage_fraction(aoi_box, geometry_bbox(o.get("geometry")))
        full = cov >= 0.98
        acquired = _parse_instant((o.get("scene") or {}).get("acquired_at"))
        ts = acquired.timestamp() if acquired else float("-inf")
        return (full, round(cov, 3) if not full else 1.0, ts)

    return sorted(usable, key=key, reverse=True)


def sensor_of(obs: Dict[str, Any]) -> str:
    return "S1_SAR" if _is_sar(obs) else "S2_OPTICAL"


# ── Public (redacted) views ───────────────────────────────────────────────────


def strip_signature(url: str) -> str:
    """Drop the query string (SAS token) from a signed https URL."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if parts.scheme in ("http", "https") and parts.query:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return url


def redact_signed_urls(value: Any) -> Any:
    """Deep-copy ``value`` with every signed URL's query string removed.

    Planetary Computer asset links carry a time-limited SAS token. The agent
    needs them internally to call inference; nothing public (the run API, the
    WebSocket stream) needs the token, so it is removed before leaving the
    service.
    """
    if isinstance(value, dict):
        return {k: redact_signed_urls(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_signed_urls(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_signed_urls(v) for v in value)
    if isinstance(value, str) and value.startswith(("http://", "https://")) and "sig=" in value:
        return strip_signature(value)
    return value
