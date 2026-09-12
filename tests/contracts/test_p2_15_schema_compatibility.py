"""
tests/contracts/test_p2_15_schema_compatibility.py
Contract compatibility tests for P2-15: EvalCase and EvalReport.
"""

import pytest
from evals.agent.harness import EvalCase, EvalReport


@pytest.mark.contract
def test_p2_15_schema_compatibility():
    """EvalCase and EvalReport schemas conform to testing harness contract."""
    case_schema = EvalCase.model_json_schema()
    expected_case = {"id", "prompt", "is_injection", "expected_hazard", "expected_sensor"}
    assert expected_case.issubset(case_schema["properties"].keys())

    report_schema = EvalReport.model_json_schema()
    expected_report = {
        "total_cases",
        "passed_cases",
        "injection_defense_rate",
        "grounding_rate",
        "overall_score",
        "details",
    }
    assert expected_report.issubset(report_schema["properties"].keys())
