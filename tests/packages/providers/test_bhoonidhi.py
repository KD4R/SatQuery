import pytest
from unittest.mock import patch, MagicMock
from packages.providers.bhoonidhi import BhoonidhiAdapter
from redis.exceptions import LockError

@patch("packages.providers.bhoonidhi.redis.from_url")
@patch("packages.providers.bhoonidhi.requests.Session")
def test_bhoonidhi_auth_budget_enforcement(mock_session_class, mock_redis_from_url):
    """P4-05: Verifies the 20 auth/hr distributed lock budget is strictly enforced."""
    mock_redis = MagicMock()
    mock_redis_from_url.return_value = mock_redis
    
    # Simulate a cache miss for the token
    mock_redis.get.side_effect = lambda k: "25" if "budget" in k else None
    
    adapter = BhoonidhiAdapter()
    
    with pytest.raises(RuntimeError, match="20 auths/hr budget exceeded"):
        adapter._get_auth_token()
        
    mock_session_class.return_value.post.assert_not_called()

@patch("packages.providers.bhoonidhi.redis.from_url")
@patch("packages.providers.bhoonidhi.requests.Session")
def test_bhoonidhi_offline_product_tagging(mock_session_class, mock_redis_from_url):
    """P4-05: Verifies Bhoonidhi STAC items that are 'Browse & Order' get tagged offline."""
    mock_redis = MagicMock()
    mock_redis_from_url.return_value = mock_redis
    mock_redis.get.return_value = "valid_cached_token"
    
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "features": [
            {"id": "1", "properties": {"Online": "Y"}},
            {"id": "2", "properties": {"Online": "N"}}
        ]
    }
    mock_session.post.return_value = mock_response
    
    adapter = BhoonidhiAdapter()
    features = adapter.search({"type": "Polygon", "coordinates": []}, start_date=None, end_date=None)
    
    assert "_bhoonidhi_status" not in features[0]
    assert features[1]["_bhoonidhi_status"] == "PRODUCT_OFFLINE"
