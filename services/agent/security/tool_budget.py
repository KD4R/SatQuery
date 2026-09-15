"""
security/tool_budget.py — Tool invocation budget tracking and limits.
"""

from pydantic import BaseModel, Field, field_validator
from services.agent.security.exceptions import BudgetExceededError

#: Server-side ceilings. A client may request a smaller budget, never a larger
#: one — otherwise a caller could grant itself unlimited tool calls (A01/A04).
MAX_ALLOWED_CALLS = 50
MAX_ALLOWED_DURATION_S = 300.0


class ToolBudget(BaseModel):
    """Tracks and enforces execution limits per mission run."""

    max_calls: int = Field(default=10, ge=1, description="Maximum allowed tool calls")
    max_duration_seconds: float = Field(
        default=60.0, gt=0.0, description="Max cumulative execution duration in seconds"
    )
    calls_made: int = Field(default=0, ge=0)
    total_duration_ms: float = Field(default=0.0, ge=0.0)

    @field_validator("max_calls")
    @classmethod
    def _cap_max_calls(cls, v: int) -> int:
        if v > MAX_ALLOWED_CALLS:
            raise ValueError(f"max_calls={v} exceeds server-side ceiling of {MAX_ALLOWED_CALLS}")
        return v

    @field_validator("max_duration_seconds")
    @classmethod
    def _cap_max_duration(cls, v: float) -> float:
        if v > MAX_ALLOWED_DURATION_S:
            raise ValueError(
                f"max_duration_seconds={v} exceeds server-side ceiling of {MAX_ALLOWED_DURATION_S}"
            )
        return v

    def consume(self, duration_ms: float = 0.0) -> None:
        """Consumes a tool call from budget. Raises BudgetExceededError if limit breached."""
        if self.calls_made >= self.max_calls:
            raise BudgetExceededError(
                f"Tool invocation budget exceeded: maximum {self.max_calls} calls allowed"
            )
        if (self.total_duration_ms + duration_ms) > (self.max_duration_seconds * 1000):
            raise BudgetExceededError(
                f"Execution time budget exceeded: maximum {self.max_duration_seconds}s allowed"
            )
        self.calls_made += 1
        self.total_duration_ms += duration_ms

    @property
    def remaining_calls(self) -> int:
        return max(0, self.max_calls - self.calls_made)
