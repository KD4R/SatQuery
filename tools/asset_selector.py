"""
tools/asset_selector.py — Filtering and ranking of satellite observation assets.
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field
from tools.base import BaseTool, ToolPermissionTier, ToolResult
from tools.registry import get_tool_registry


class AssetSelectorArgs(BaseModel):
    assets: List[Dict[str, Any]] = Field(..., description="Candidate scenes from STAC search")
    preferred_sensor: str = Field(default="S1_SAR", description="Preferred sensor mode")
    max_cloud_cover: float = Field(default=20.0, ge=0.0, le=100.0)


class AssetSelectorTool(BaseTool):
    name = "asset_selector"
    version = "1.0.0"
    description = "Filters and ranks candidate observation assets for optimal hazard coverage"
    permission_tier = ToolPermissionTier.READ
    args_schema = AssetSelectorArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        args = self.args_schema(**kwargs)

        if not args.assets:
            return ToolResult(success=True, output=[], metadata={"selected_count": 0})

        selected = []
        for a in args.assets:
            sensor = a.get("sensor", "")
            cloud = a.get("cloud_cover", 0.0)

            # Optical assets must satisfy max cloud cover filter
            if "OPTICAL" in sensor and cloud > args.max_cloud_cover:
                continue

            selected.append(a)

        # Sort so preferred sensor is first, then lowest cloud cover
        selected.sort(
            key=lambda x: (
                0 if x.get("sensor") == args.preferred_sensor else 1,
                x.get("cloud_cover", 0.0),
            )
        )

        return ToolResult(
            success=True,
            output=selected,
            metadata={"selected_count": len(selected), "preferred": args.preferred_sensor},
        )


# Self-register
get_tool_registry().register(AssetSelectorTool())
