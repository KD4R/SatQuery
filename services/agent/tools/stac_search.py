"""
tools/stac_search.py — Bhoonidhi / STAC catalogue observation search tool.
"""

from typing import Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field
from services.agent.tools.base import BaseTool, ToolPermissionTier, ToolResult
from services.agent.tools.registry import get_tool_registry
from services.eo_data.search import search_service


class STACSearchArgs(BaseModel):
    bbox: List[float] = Field(
        ..., min_length=4, max_length=4, description="[min_lon, min_lat, max_lon, max_lat]"
    )
    start_date: str = Field(..., description="ISO 8601 start date")
    end_date: str = Field(..., description="ISO 8601 end date")
    sensors: List[str] = Field(
        default_factory=lambda: ["S1_SAR", "S2_OPTICAL"], description="Sensors to search"
    )
    max_cloud_cover: float = Field(default=30.0, ge=0.0, le=100.0)


class STACSearchTool(BaseTool):
    name = "stac_search"
    version = "1.0.0"
    description = "Searches Bhoonidhi and STAC catalogues for EO satellite observations"
    permission_tier = ToolPermissionTier.READ
    args_schema = STACSearchArgs

    def execute(self, **kwargs: Any) -> ToolResult:
        args = self.args_schema(**kwargs)

        # Validate bbox coordinate bounds
        min_lon, min_lat, max_lon, max_lat = args.bbox
        if not (-180.0 <= min_lon <= 180.0 and -180.0 <= max_lon <= 180.0):
            raise ValueError(f"Longitude out of bounds in bbox: {args.bbox}")
        if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
            raise ValueError(f"Latitude out of bounds in bbox: {args.bbox}")

        results: List[Dict[str, Any]] = []

        try:
            start = datetime.fromisoformat(args.start_date.replace("Z", "+00:00"))
            end = datetime.fromisoformat(args.end_date.replace("Z", "+00:00"))

            geo_polygon = {
                "type": "Polygon",
                "coordinates": [
                    [
                        [min_lon, min_lat],
                        [max_lon, min_lat],
                        [max_lon, max_lat],
                        [min_lon, max_lat],
                        [min_lon, min_lat],
                    ]
                ],
            }

            # Call P4 search service (defaults to bhoonidhi internally if not specified,
            # we will just use bhoonidhi for now)
            observations = search_service.search_observations(
                provider_name="bhoonidhi",
                polygon=geo_polygon,
                start_date=start,
                end_date=end,
                cloud_cover=args.max_cloud_cover,
                context={},
            )

            for obs in observations:
                obs_sensor = obs.normalized_properties.get("sensor", "")
                if not args.sensors or obs_sensor in args.sensors:
                    dump = obs.model_dump()
                    # Ensure sensor is top-level for downstream consumers
                    dump.setdefault("sensor", obs_sensor)
                    results.append(dump)

        except Exception as e:
            return ToolResult(success=False, output=[], metadata={"error": str(e)})

        return ToolResult(
            success=True,
            output=results,
            metadata={"matched_scenes": len(results), "sensors": args.sensors},
        )


# Self-register
get_tool_registry().register(STACSearchTool())
