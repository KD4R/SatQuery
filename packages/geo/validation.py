import logging
import json
from urllib.parse import urlparse
from typing import Dict, Any
from shapely.geometry import shape

logger = logging.getLogger(__name__)

# Strict security boundaries against SSRF (Issue P4-19)
ALLOWED_PROTOCOLS = {"https", "s3"}

ALLOWED_DOMAINS = {
    # ISRO / Bhoonidhi -- exact host, not a suffix rule
    "bhoonidhi-api.nrsc.gov.in",
    # Microsoft Planetary Computer
    "planetarycomputer.microsoft.com",
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
    # ASF / NASA
    "datapool.asf.alaska.edu",
    "hyp3-api.asf.alaska.edu",
    # Copernicus Data Space Ecosystem
    "zipper.dataspace.copernicus.eu",
    "stac.dataspace.copernicus.eu",
}

def validate_asset_href(href: str) -> str:
    """
    Implements P4-09: Secure asset retrieval.
    Validates asset href to prevent SSRF and restrict to trusted sources.
    Matches parsed.hostname strictly.
    """
    parsed = urlparse(href)
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        raise ValueError(f"Security error: protocol {parsed.scheme} is not allowed.")
    
    if parsed.scheme == "https":
        if parsed.hostname not in ALLOWED_DOMAINS:
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
            raise ValueError("Invalid geometry topology (e.g., self-intersecting polygons).")
    except Exception as e:
        raise ValueError(f"Malformed geometry: {str(e)}")
        
    return geometry
