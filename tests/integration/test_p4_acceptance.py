import pytest
from datetime import datetime, timezone
from services.eo_data.search import search_service
from services.eo_data.api import resolve_asset_api, ResolveRequest
from packages.contracts.ml import AssetRef


@pytest.mark.integration
def test_provider_outage_raises_error(monkeypatch):
    """Ensure upstream failure returns a clear error without fixture fallback."""

    def mock_search(*args, **kwargs):
        raise TimeoutError("Upstream timeout")

    monkeypatch.setattr(search_service.bhoonidhi, "search", mock_search)

    with pytest.raises(TimeoutError, match="Upstream timeout"):
        search_service.search_observations(
            provider_name="bhoonidhi",
            polygon={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            context={},
        )


@pytest.mark.integration
def test_quality_rejection_raises_error(monkeypatch):
    """Ensure low quality assets (e.g., 100% cloud cover) raise an explicit ValueError."""

    def mock_search(*args, **kwargs):
        return [{"id": "bad", "properties": {"eo:cloud_cover": 100.0}}]

    monkeypatch.setattr(search_service.bhoonidhi, "search", mock_search)
    with pytest.raises(ValueError, match="rejected due to poor Data Quality"):
        search_service.search_observations(
            provider_name="bhoonidhi",
            polygon={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            context={},
        )


@pytest.mark.integration
def test_real_raster_acceptance():
    """Ensure AssetRef is fully populated on asset resolution."""
    req = ResolveRequest(provider="bhoonidhi", item_id="test_item", asset_key="test_asset")

    # We mock get_asset to just return a dummy s3 URI instead of actually downloading
    class DummyAdapter:
        def get_asset(self, item_id, asset_key, context):
            return f"s3://satquery/assets/{item_id}/{asset_key}.tif"

    import packages.providers.bhoonidhi

    original = packages.providers.bhoonidhi.BhoonidhiAdapter
    packages.providers.bhoonidhi.BhoonidhiAdapter = DummyAdapter

    try:
        res = resolve_asset_api(req, org_id="org_123")
        assert isinstance(res, AssetRef)
        assert res.s3_uri == "s3://satquery/assets/test_item/test_asset.tif"
        assert "localhost" in res.titiler_url or "titiler" in res.titiler_url
        assert "url=s3://satquery/assets/test_item/test_asset.tif" in res.titiler_url
    finally:
        packages.providers.bhoonidhi.BhoonidhiAdapter = original
