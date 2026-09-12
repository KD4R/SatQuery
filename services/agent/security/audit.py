"""
security/audit.py — Tool call auditing and secret redaction.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

_SENSITIVE_KEYS = re.compile(r"(token|secret|password|key|auth|credential)", re.I)


class ToolAuditEntry(BaseModel):
    audit_id: str
    tool_name: str
    caller: str
    organization_id: str
    sanitized_args: Dict[str, Any] = Field(default_factory=dict)
    status: str
    execution_time_ms: float = Field(ge=0.0)
    trace_id: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class AuditLogger:
    """Logs tool calls with sensitive parameter redaction and organization scoping."""

    def __init__(self):
        self._entries: List[ToolAuditEntry] = []

    def _redact_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        redacted: Dict[str, Any] = {}
        for k, v in args.items():
            if _SENSITIVE_KEYS.search(k):
                redacted[k] = "[REDACTED]"
            elif isinstance(v, dict):
                redacted[k] = self._redact_args(v)
            else:
                redacted[k] = v
        return redacted

    def log_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        caller: str,
        org_id: str,
        status: str,
        execution_time_ms: float,
        trace_id: Optional[str] = None,
    ) -> ToolAuditEntry:
        if not tool_name:
            raise ValueError("tool_name cannot be empty")
        if not org_id:
            raise ValueError("org_id cannot be empty")

        entry = ToolAuditEntry(
            audit_id=f"audit_{uuid.uuid4().hex[:10]}",
            tool_name=tool_name,
            caller=caller,
            organization_id=org_id,
            sanitized_args=self._redact_args(args),
            status=status,
            execution_time_ms=execution_time_ms,
            trace_id=trace_id,
        )
        self._entries.append(entry)
        return entry

    def get_entries(self, org_id: Optional[str] = None) -> List[ToolAuditEntry]:
        if org_id:
            return [e for e in self._entries if e.organization_id == org_id]
        return list(self._entries)


_global_audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    return _global_audit_logger
