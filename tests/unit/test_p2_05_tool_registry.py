"""
tests/unit/test_p2_05_tool_registry.py
Unit tests for P2-05: Versioned tool registry and schemas.
"""

from typing import Any
import pytest
from pydantic import BaseModel, Field

from tools.base import BaseTool, ToolPermissionTier, ToolResult
from tools.registry import ToolRegistry


class DummySearchArgs(BaseModel):
    query: str = Field(..., min_length=2)
    limit: int = Field(default=10, ge=1, le=100)


class DummySearchToolV1(BaseTool):
    name = "stac_search"
    version = "1.0.0"
    description = "Search STAC metadata items"
    permission_tier = ToolPermissionTier.READ
    args_schema = DummySearchArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        args = self.args_schema(**kwargs)
        return ToolResult(
            success=True,
            output=[{"id": f"scene-{i}", "q": args.query} for i in range(args.limit)],
        )


class DummySearchToolV2(BaseTool):
    name = "stac_search"
    version = "2.0.0"
    description = "Advanced search STAC metadata items with filtering"
    permission_tier = ToolPermissionTier.READ
    args_schema = DummySearchArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(success=True, output=["advanced-scene"])


@pytest.mark.unit
def test_versioned_tool_registry_and_schemas_valid():
    """Tool registration, semantic version resolution, and argument validation succeed."""
    registry = ToolRegistry()
    t1 = DummySearchToolV1()
    t2 = DummySearchToolV2()

    registry.register(t1)
    registry.register(t2)

    # Get by explicit version
    assert registry.get("stac_search", "1.0.0").version == "1.0.0"
    # Get latest version defaults to 2.0.0
    assert registry.get("stac_search").version == "2.0.0"

    # Validate arguments against schema
    validated = registry.validate_args("stac_search", {"query": "Brahmaputra", "limit": 5})
    assert validated.query == "Brahmaputra"  # type: ignore[attr-defined]
    assert validated.limit == 5  # type: ignore[attr-defined]

    # Inspect schema
    schemas = registry.list_tools()
    assert len(schemas) == 2
    assert any(s["version"] == "1.0.0" and "parameters" in s for s in schemas)


@pytest.mark.unit
def test_versioned_tool_registry_and_schemas_invalid_input():
    """Unregistered tools, invalid versions, and malformed arguments raise errors."""
    registry = ToolRegistry()
    registry.register(DummySearchToolV1())

    # Unregistered tool name
    with pytest.raises(KeyError, match="not registered"):
        registry.get("nonexistent_tool")

    # Unregistered version
    with pytest.raises(KeyError, match="version '9.9.9' is not registered"):
        registry.get("stac_search", "9.9.9")

    # Invalid arguments (limit < 1 fails ge=1 constraint)
    with pytest.raises(ValueError, match="Invalid arguments for tool"):
        registry.validate_args("stac_search", {"query": "valid", "limit": -5})
