from unittest.mock import patch, MagicMock
from packages.geo.postgis import PostGISOperations


@patch("packages.geo.postgis.pool.ThreadedConnectionPool")
def test_postgis_rls_tenant_isolation(mock_pool_class):
    """P4-14: Verifies PostGIS operations rigorously enforce and clean up Row-Level Security contexts."""  # noqa: E501
    mock_pool = MagicMock()
    mock_pool_class.return_value = mock_pool

    mock_conn = MagicMock()
    mock_conn.closed = 0
    mock_pool.getconn.return_value = mock_conn
    mock_cursor = MagicMock()
    # Support context manager
    mock_cursor.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value = mock_cursor

    ops = PostGISOperations()

    ops.insert_aoi("org_abc", "aoi_123", "Test", {"type": "Point", "coordinates": [0, 0]})

    # Verify set_config was called with org_abc BEFORE the insert
    assert (
        mock_cursor.execute.call_args_list[0][0][0]
        == "SELECT set_config('satquery.org_id', %s, false);"
    )
    assert mock_cursor.execute.call_args_list[0][0][1] == ("org_abc",)

    # Verify the insert query
    assert "INSERT INTO aois" in mock_cursor.execute.call_args_list[1][0][0]

    # Verify the cleanup in the finally block resets to empty string
    assert (
        mock_cursor.execute.call_args_list[-1][0][0]
        == "SELECT set_config('satquery.org_id', '', false);"
    )

    # Verify connection was put back
    mock_pool.putconn.assert_called_once_with(mock_conn, close=False)
