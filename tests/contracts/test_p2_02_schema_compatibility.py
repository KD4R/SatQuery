"""
tests/contracts/test_p2_02_schema_compatibility.py
Contract compatibility tests for P2-02 security & error schema responses.
"""

import pytest
from packages.contracts.errors import ErrorDetail, ErrorResponse
from services.agent.security.exceptions import GeometryValidationError, PromptInjectionError


@pytest.mark.contract
def test_p2_02_schema_compatibility():
    """Security exception errors adhere strictly to canonical ErrorResponse contract."""
    inj_err = PromptInjectionError("Pattern matched prompt injection rule")
    resp = ErrorResponse(
        code=inj_err.code,
        message=inj_err.message,
        details=[ErrorDetail(message=inj_err.message, code=inj_err.code)],
        retryable=False,
        trace_id="tr-test-security-001",
    )
    data = resp.model_dump()
    assert data["code"] == "PROMPT_INJECTION_DETECTED"
    assert data["retryable"] is False
    assert data["trace_id"] == "tr-test-security-001"
    assert len(data["details"]) == 1

    geom_err = GeometryValidationError("Polygon exterior ring is not closed")
    geom_resp = ErrorResponse(
        code=geom_err.code,
        message=geom_err.message,
        details=[ErrorDetail(message=geom_err.message, code=geom_err.code)],
        retryable=False,
    )
    geom_data = geom_resp.model_dump()
    assert geom_data["code"] == "INVALID_GEOMETRY"
