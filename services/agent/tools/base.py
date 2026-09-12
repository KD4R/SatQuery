"""
tools/base.py — Base tool definitions, results, and interfaces.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field


class ToolPermissionTier(str, Enum):
    READ = "read"
    EXECUTE = "execute"
    ADMIN = "admin"


class ToolResult(BaseModel):
    """Canonical result object returned by any registered tool execution."""

    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for all versioned tools in the agent registry."""

    name: str
    version: str = "1.0.0"
    description: str
    permission_tier: ToolPermissionTier = ToolPermissionTier.READ
    args_schema: Type[BaseModel]

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Executes the tool with validated arguments."""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Returns JSON schema representation of the tool's input contract."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "permission_tier": self.permission_tier.value,
            "parameters": self.args_schema.model_json_schema(),
        }
