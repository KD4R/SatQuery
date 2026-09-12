"""
security package — Defenses, sanitization, validation, budgets, and audit for SatQuery AI.
"""

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
    "BudgetExceededError",
    "GeometryValidationError",
    "PromptInjectionError",
    "SecurityError",
    "ToolBudget",
    "ToolPermissionDeniedError",
    "check_prompt_injection",
    "sanitize_prompt",
    "validate_aoi_geometry",
    "validate_intent",
]
