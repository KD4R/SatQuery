"""
security/validator.py — GeoJSON and Intent validation for agent inputs.
"""

from typing import Any, Dict, List
from services.agent.security.exceptions import GeometryValidationError

_SUPPORTED_DISASTERS = {
    "flood",
    "wildfire",
    "cyclone",
    "landslide",
    "earthquake",
    "inundation",
}

#: GeoJSON coordinates are at most 4 levels deep (position/ring/polygon/
#: multipolygon). A deeper nesting is malformed input or a recursion-bomb
#: attempt (A04) — reject before Python's own RecursionError becomes a 500.
_MAX_COORDINATE_DEPTH = 4


def _validate_coordinates(coords: List[Any], depth: int = 0) -> None:
    """Recursively validates coordinate pairs are within geographic boundaries."""
    if depth > _MAX_COORDINATE_DEPTH:
        raise GeometryValidationError(
            f"Coordinates nested deeper than {_MAX_COORDINATE_DEPTH} levels"
        )

    if not coords:
        raise GeometryValidationError("Coordinate list cannot be empty")

    # If list of two numbers [lon, lat]
    if len(coords) >= 2 and all(isinstance(c, (int, float)) for c in coords[:2]):
        lon, lat = coords[0], coords[1]
        if not (-180.0 <= lon <= 180.0):
            raise GeometryValidationError(f"Longitude {lon} out of valid bounds [-180, 180]")
        if not (-90.0 <= lat <= 90.0):
            raise GeometryValidationError(f"Latitude {lat} out of valid bounds [-90, 90]")
        return

    for item in coords:
        if isinstance(item, list):
            _validate_coordinates(item, depth + 1)
        else:
            raise GeometryValidationError(f"Malformed coordinate element: {item}")


def validate_aoi_geometry(geojson: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates GeoJSON Area of Interest structure, coordinate ranges, and polygon closure.
    """
    if not isinstance(geojson, dict):
        raise GeometryValidationError("AOI must be a valid GeoJSON dictionary")

    geom_type = geojson.get("type")
    if not geom_type:
        raise GeometryValidationError("GeoJSON missing 'type' attribute")

    if geom_type not in {"Polygon", "MultiPolygon", "Feature", "FeatureCollection"}:
        raise GeometryValidationError(
            f"Unsupported GeoJSON type '{geom_type}'. Must be Polygon or Feature"
        )

    if geom_type == "Polygon":
        coords = geojson.get("coordinates")
        if not coords or not isinstance(coords, list):
            raise GeometryValidationError("Polygon missing valid coordinates array")

        # Validate closure of exterior ring
        exterior_ring = coords[0]
        if len(exterior_ring) < 4:
            raise GeometryValidationError(
                f"Polygon exterior ring must have at least 4 coordinates, got {len(exterior_ring)}"
            )

        if exterior_ring[0] != exterior_ring[-1]:
            raise GeometryValidationError("Polygon exterior ring is not closed (first != last)")

        _validate_coordinates(coords)

    elif geom_type == "Feature":
        geom = geojson.get("geometry")
        if not geom or not isinstance(geom, dict):
            raise GeometryValidationError("Feature missing 'geometry' object")
        validate_aoi_geometry(geom)

    return geojson


def validate_intent(intent: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates extracted mission intent for supported disaster domains.
    """
    if not isinstance(intent, dict):
        raise ValueError("Intent must be a dictionary")

    disaster = intent.get("disaster_type", "").lower()
    if disaster and disaster not in _SUPPORTED_DISASTERS:
        raise ValueError(
            f"Unsupported disaster type '{disaster}'. Allowed: {sorted(_SUPPORTED_DISASTERS)}"
        )

    return intent
