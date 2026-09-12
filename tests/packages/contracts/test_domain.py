import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from packages.contracts.data import SceneRef, Observation

def test_sceneref_valid_creation():
    """P4-03: Tests valid SceneRef model creation"""
    scene = SceneRef(
        provider="bhoonidhi",
        collection="EOS-04",
        item_id="123",
        acquired_at=datetime.now(timezone.utc),
        platform="EOS-04",
        instrument="SAR",
        stac_href="https://example.com/stac",
        relative_orbit=42,
        pass_direction="ASCENDING"
    )
    assert scene.provider == "bhoonidhi"
    assert scene.cloud_cover is None  # Defaults to None

def test_observation_invalid_missing_fields():
    """P4-03: Tests Observation model fails securely on missing canonical fields"""
    with pytest.raises(ValidationError):
        Observation(
            observation_id="123",
            # Missing scene
            geometry={"type": "Polygon", "coordinates": []},
            assets={"vh": "s3://bucket/vh.tif"}
        )
