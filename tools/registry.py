"""
tools/registry.py — Semantic versioned tool registry for SatQuery AI.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ValidationError
from tools.base import BaseTool


class ToolRegistry:
    """
    Registry maintaining semantic-versioned tools and their input schemas.
    """

    def __init__(self):
        # Key: (tool_name, version)
        self._tools: Dict[tuple, BaseTool] = {}
        # Key: tool_name -> latest_version
        self._latest_versions: Dict[str, str] = {}

    def register(self, tool: BaseTool) -> None:
        key = (tool.name, tool.version)
        self._tools[key] = tool
        # Track latest registered version
        self._latest_versions[tool.name] = tool.version

    def get(self, name: str, version: Optional[str] = None) -> BaseTool:
        v = version or self._latest_versions.get(name)
        if not v:
            raise KeyError(f"Tool '{name}' is not registered")
        key = (name, v)
        if key not in self._tools:
            raise KeyError(f"Tool '{name}' version '{v}' is not registered")
        return self._tools[key]

    def list_tools(self) -> List[Dict[str, Any]]:
        return [tool.get_schema() for tool in self._tools.values()]

    def validate_args(
        self, name: str, args: Dict[str, Any], version: Optional[str] = None
    ) -> BaseModel:
        tool = self.get(name, version)
        try:
            return tool.args_schema(**args)
        except ValidationError as exc:
            raise ValueError(
                f"Invalid arguments for tool '{name}' (v{tool.version}): {exc}"
            ) from exc


_global_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _global_registry
