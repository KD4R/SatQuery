import logging
from typing import Optional
from datetime import datetime, timedelta

from packages.contracts import Observation
from services.eo_data.search import search_service

logger = logging.getLogger(__name__)


def get_latest_observation_for_mission(
    provider_name: str,
    aoi_polygon: dict,
    last_run_date: datetime,
    cadence_days: int = 7,
    max_cloud_cover: float = 30.0,
) -> Optional[Observation]:
    """
    Implements P4-18: Monitoring observation selection support.
    Selects the most suitable recent observation for a recurring monitoring mission,
    looking within the cadence window.
    """
    target_start = last_run_date
    target_end = last_run_date + timedelta(days=cadence_days)

    logger.info(
        f"Looking for monitoring observation between {target_start.isoformat()} and {target_end.isoformat()}"  # noqa: E501
    )

    try:
        observations = search_service.search_observations(
            polygon=aoi_polygon,
            start_date=target_start,
            end_date=target_end,
            context={"source": "monitoring_hook"},
            cloud_cover=max_cloud_cover,
            provider_name=provider_name,
        )
    except Exception as e:
        logger.error(f"Failed to fetch monitoring observations: {e}")
        return None

    # Filter out offline products for automated monitoring paths
    available = [
        obs
        for obs in observations
        if obs.normalized_properties.get("offline_status") != "PRODUCT_OFFLINE"
    ]

    if not available:
        logger.info("No suitable online observations found for this monitoring cycle.")
        return None

    # Sort by cloud cover (lowest first) and acquisition date (most recent first)
    # Using scene.cloud_cover with a fallback of 100 if None
    available.sort(key=lambda o: (o.scene.cloud_cover or 100.0, -o.scene.acquired_at.timestamp()))

    selected = available[0]
    logger.info(
        f"Selected observation {selected.observation_id} acquired at {selected.scene.acquired_at}"
    )
    return selected  # type: ignore
