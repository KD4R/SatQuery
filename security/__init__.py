"""
security package — Defenses, sanitization, validation, budgets, and audit for SatQuery AI.
"""

from security.audit import AuditLogger, ToolAuditEntry, get_audit_logger
from security.exceptions import (
    BudgetExceededError,
    GeometryValidationError,
    PromptInjectionError,
    SecurityError,
    ToolPermissionDeniedError,
)
from security.sanitizer import check_prompt_injection, sanitize_prompt
from security.tool_budget import ToolBudget
from security.validator import validate_aoi_geometry, validate_intent

__all__ = [
    "AuditLogger",
    "BudgetExceededError",
    "GeometryValidationError",
    "PromptInjectionError",
    "SecurityError",
    "ToolAuditEntry",
    "ToolBudget",
    "ToolPermissionDeniedError",
    "check_prompt_injection",
    "get_audit_logger",
    "sanitize_prompt",
    "validate_aoi_geometry",
    "validate_intent",
]
