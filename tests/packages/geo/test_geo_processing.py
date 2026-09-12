import pytest

from packages.geo.validation import validate_asset_href, validate_geojson_geometry


def test_validate_asset_href_blocks_ssrf():
    # Valid NRSC domain
    assert validate_asset_href("https://bhoonidhi-api.nrsc.gov.in/data/123.tif")

    # Valid S3 domain
    assert validate_asset_href("https://sentinel-cogs.s3.us-west-2.amazonaws.com/123.tif")

    # Blocked domains / SSRF attempts
    with pytest.raises(ValueError, match="not allowlisted"):
        validate_asset_href("https://malicious-domain.com/steal?token=123")

    with pytest.raises(ValueError, match="not allowed"):
        validate_asset_href("file:///etc/passwd")


def test_validate_geojson_geometry_blocks_complex_payloads():
    # Valid simple geometry
    valid_geom = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
    assert validate_geojson_geometry(valid_geom) == valid_geom

    # Block invalid topology
    invalid_geom = {
        "type": "Polygon",
        # Self-intersecting bowtie
        "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]],
    }
    with pytest.raises(ValueError, match="Invalid geometry topology"):
        validate_geojson_geometry(invalid_geom)

    # Block massive vertex counts
    massive_geom = {"type": "Polygon", "coordinates": [[[i, i] for i in range(15000)]]}
    with pytest.raises(ValueError, match="maximum vertex complexity"):
        validate_geojson_geometry(massive_geom)
