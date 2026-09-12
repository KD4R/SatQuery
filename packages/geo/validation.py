import logging
import json
from urllib.parse import urlparse
from typing import Dict, Any
from shapely.geometry import shape

logger = logging.getLogger(__name__)

# Strict security boundaries against SSRF
ALLOWED_PROTOCOLS = {"http", "https", "s3"}
ALLOWED_DOMAINS = {
    "planetarycomputer.microsoft.com",
    "sentinel-cogs.s3.us-west-2.amazonaws.com"
}

def validate_asset_href(href: str) -> str:
    """
    Implements P4-09: Secure asset retrieval.
    Validates asset href to prevent SSRF and restrict to trusted sources.
    """
    parsed = urlparse(href)
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        raise ValueError(f"Security error: protocol {parsed.scheme} is not allowed.")
    
    if parsed.scheme in ["http", "https"]:
        # Allowlist check, permitting NRSC domains by pattern
        if parsed.hostname not in ALLOWED_DOMAINS and not (parsed.hostname and parsed.hostname.endswith(".nrsc.gov.in")):
            logger.warning(f"SSRF blocked: Attempt to access unauthorized domain {parsed.hostname}")
            raise ValueError(f"Security error: Domain {parsed.hostname} is not allowlisted.")
            
    return href

def validate_geojson_geometry(geometry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates GeoJSON to ensure payload is structurally sound for spatial operations,
    and prevents DoS attacks via geometry-complexity limits.
    """
    if not isinstance(geometry, dict):
        raise ValueError("Geometry must be a dictionary")
    if "type" not in geometry or "coordinates" not in geometry:
        raise ValueError("Invalid GeoJSON geometry structure")
        
    # 1. Complexity limits (DoS protection)
    # Check string representation as a fast proxy for deep nesting / huge vertex counts
    geom_str = json.dumps(geometry)
    if geom_str.count("[") > 10000:
        logger.warning("GeoJSON validation failed: Vertex count exceeds complexity limits.")
        raise ValueError("Geometry exceeds maximum vertex complexity limits.")
        
    # 2. Topological validation using Shapely
    try:
        s = shape(geometry)
        if not s.is_valid:
            # Attempt to buffer by 0 to fix minor topological errors (e.g. self-intersections)
            s = s.buffer(0)
            if not s.is_valid:
                raise ValueError("Invalid geometry topology (e.g., self-intersecting polygons).")
    except Exception as e:
        raise ValueError(f"Malformed geometry: {str(e)}")
        
    return geometry
