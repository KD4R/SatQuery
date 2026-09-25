"""
nodes/resilience.py — Agent failure detection, bounded retries, and deterministic fallback recovery.
"""

from typing import Any, Callable, Optional
from pydantic import BaseModel, Field


class RecoveryResult(BaseModel):
    success: bool
    used_fallback: bool
    retries_attempted: int = Field(ge=0)
    data: Any
    status: str
    warning: Optional[str] = None


def execute_with_recovery(
    action_name: str,
    primary_fn: Callable[[], Any],
    max_retries: int = 2,
) -> RecoveryResult:
    """
    Executes an upstream operation with bounded retries. Upstream failure returns a clear failure.
    Never silently fabricates success or uses fallbacks.
    """
    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")
    if not action_name:
        raise ValueError("action_name cannot be empty")

    attempts = 0
    last_error: Optional[Exception] = None

    while attempts <= max_retries:
        try:
            res = primary_fn()
            return RecoveryResult(
                success=True,
                used_fallback=False,
                retries_attempted=attempts,
                data=res,
                status="HEALTHY",
            )
        except Exception as exc:
            attempts += 1
            last_error = exc

    # Primary failed after retries — return clear failure
    return RecoveryResult(
        success=False,
        used_fallback=False,
        retries_attempted=attempts - 1,
        data=None,
        status="FAILED",
        warning=f"Upstream {action_name} failed after {max_retries} retries ({last_error})",
    )
