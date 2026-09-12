"""
tests/contracts/test_p2_04_schema_compatibility.py
Contract compatibility tests for P2-04: ExecuteRequest and ExecuteResponse.
"""

import pytest
from services.agent.schemas import ExecuteRequest, ExecuteResponse


@pytest.mark.contract
def test_p2_04_schema_compatibility():
    """ExecuteRequest and ExecuteResponse schemas conform to contracts."""
    req_schema = ExecuteRequest.model_json_schema()
    assert {"query", "mission_id", "aoi", "temporal_window", "budget"}.issubset(
        req_schema["properties"].keys()
    )

    resp_schema = ExecuteResponse.model_json_schema()
    assert {"job_id", "mission_id", "status", "message", "trace_id"}.issubset(
        resp_schema["properties"].keys()
    )
