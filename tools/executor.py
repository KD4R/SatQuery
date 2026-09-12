"""
tools/executor.py — Permission-aware tool execution with RBAC and budget controls.
"""

import time
from typing import Any, Dict, Optional
from packages.auth.models import AuthContext, Role
from security.exceptions import ToolPermissionDeniedError
from security.tool_budget import ToolBudget
from tools.base import ToolPermissionTier, ToolResult
from tools.registry import ToolRegistry, get_tool_registry

_ROLE_PERMITTED_TIERS = {
    Role.ADMIN: {ToolPermissionTier.READ, ToolPermissionTier.EXECUTE, ToolPermissionTier.ADMIN},
    Role.OPERATOR: {ToolPermissionTier.READ, ToolPermissionTier.EXECUTE},
    Role.ANALYST: {ToolPermissionTier.READ, ToolPermissionTier.EXECUTE},
    Role.VIEWER: {ToolPermissionTier.READ},
}


class ToolExecutor:
    """Executes tools after validating caller authorization and budget allocations."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or get_tool_registry()

    def _check_permission(self, tier: ToolPermissionTier, auth_context: AuthContext) -> None:
        if auth_context.is_admin:
            return

        # Check all roles user possesses
        allowed_tiers = set()
        for r in auth_context.roles:
            allowed_tiers.update(_ROLE_PERMITTED_TIERS.get(r, {ToolPermissionTier.READ}))

        if tier not in allowed_tiers:
            raise ToolPermissionDeniedError(
                f"User lacks required role to invoke tool requiring '{tier.value}' permission"
            )

    def execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        auth_context: AuthContext,
        budget: Optional[ToolBudget] = None,
        version: Optional[str] = None,
    ) -> ToolResult:
        tool = self.registry.get(tool_name, version)
        self._check_permission(tool.permission_tier, auth_context)

        # Pre-check budget before execution
        if budget:
            budget.consume(0.0)

        # Validate arguments against Pydantic schema
        validated_args = self.registry.validate_args(tool_name, args, version)

        start = time.perf_counter()
        result = tool.execute(**validated_args.model_dump())
        duration_ms = (time.perf_counter() - start) * 1000
        result.execution_time_ms = round(duration_ms, 2)

        if budget:
            budget.total_duration_ms += duration_ms

        # Record audit log and observability metrics
        from packages.observability import get_agent_metrics
        from security.audit import get_audit_logger

        get_audit_logger().log_tool_call(
            tool_name=tool_name,
            args=args,
            caller=auth_context.subject,
            org_id=auth_context.organisation_id,
            status="success" if result.success else "error",
            execution_time_ms=result.execution_time_ms,
            trace_id=auth_context.trace_id,
        )
        get_agent_metrics().record_tool_call(
            tool_name=tool_name, status="success" if result.success else "error"
        )

        return result


_global_executor = ToolExecutor()


def get_tool_executor() -> ToolExecutor:
    return _global_executor
