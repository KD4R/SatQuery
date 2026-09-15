"""
tests/unit/test_p2_06_tool_executor.py
Unit tests for P2-06: Permission-aware tool executor and budgets.
"""

from typing import Any
import pytest
from pydantic import BaseModel

from packages.auth.models import AuthContext, Role
from services.agent.security.exceptions import BudgetExceededError, ToolPermissionDeniedError
from services.agent.security.tool_budget import ToolBudget
from services.agent.tools.base import BaseTool, ToolPermissionTier, ToolResult
from services.agent.tools.executor import ToolExecutor
from services.agent.tools.registry import ToolRegistry


class _TestArgs(BaseModel):
    action: str = "run"


class _ExecutionTool(BaseTool):
    name = "sar_processor"
    version = "1.0.0"
    description = "Runs compute-intensive SAR processing"
    permission_tier = ToolPermissionTier.EXECUTE
    args_schema = _TestArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True, output="sar_done")


def _make_context(role: Role) -> AuthContext:
    return AuthContext(
        subject="usr_test",
        organisation_id="org_test",
        roles=[role],
        email="test@satquery.com",
        trace_id="test_trace",
    )


@pytest.mark.unit
def test_permission_aware_tool_executor_and_budgets_valid():
    """Authorized analyst executes tool successfully and budget counts increment."""
    registry = ToolRegistry()
    registry.register(_ExecutionTool())
    executor = ToolExecutor(registry)

    budget = ToolBudget(max_calls=3)
    analyst_ctx = _make_context(Role.ANALYST)

    res = executor.execute_tool("sar_processor", {"action": "run"}, analyst_ctx, budget=budget)
    assert res.success is True
    assert res.output == "sar_done"
    assert budget.calls_made == 1
    assert budget.remaining_calls == 2


@pytest.mark.unit
def test_permission_aware_tool_executor_and_budgets_invalid_input():
    """Viewer is rejected from execute-tier tool; exceeding budget raises BudgetExceededError."""
    registry = ToolRegistry()
    registry.register(_ExecutionTool())
    executor = ToolExecutor(registry)

    # 1. Permission check failure: viewer cannot run EXECUTE tier
    viewer_ctx = _make_context(Role.VIEWER)
    with pytest.raises(ToolPermissionDeniedError, match="User lacks required role"):
        executor.execute_tool("sar_processor", {"action": "run"}, viewer_ctx)

    # 2. Budget exceeded failure
    budget = ToolBudget(max_calls=1)
    admin_ctx = _make_context(Role.ADMIN)
    # First call succeeds
    executor.execute_tool("sar_processor", {"action": "run"}, admin_ctx, budget=budget)
    assert budget.calls_made == 1

    # Second call breaches budget
    with pytest.raises(BudgetExceededError, match="budget exceeded"):
        executor.execute_tool("sar_processor", {"action": "run"}, admin_ctx, budget=budget)
