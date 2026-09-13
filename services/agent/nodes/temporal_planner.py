"""
nodes/temporal_planner.py — Pre-event baseline and crisis post-event temporal planning node.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from pydantic import BaseModel, Field


class TemporalWindow(BaseModel):
    start_date: str
    end_date: str
    label: str


class TemporalPlan(BaseModel):
    event_date: str
    baseline_window: TemporalWindow
    crisis_window: TemporalWindow
    sensor_match_strategy: str = "SAME_ORBIT_PASS"
    recommended_pairing: Dict[str, Any] = Field(default_factory=dict)


def compute_temporal_plan(
    event_date_str: str,
    baseline_days_prior: int = 20,
    crisis_window_days: int = 5,
    hazard_type: str = "flood",
) -> TemporalPlan:
    """
    Computes pre-event baseline and crisis temporal windows with sensor orbit pairing.
    """
    if baseline_days_prior <= 0:
        raise ValueError("baseline_days_prior must be positive")
    if crisis_window_days <= 0:
        raise ValueError("crisis_window_days must be positive")

    try:
        # Parse ISO date or YYYY-MM-DD
        if "T" in event_date_str:
            dt = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(event_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception as exc:
        raise ValueError(f"Invalid event date format '{event_date_str}': {exc}") from exc

    # Crisis window: [event_date - 1 day, event_date + (crisis_window_days - 1)]
    crisis_start = dt - timedelta(days=1)
    crisis_end = dt + timedelta(days=crisis_window_days - 1)

    # Baseline window: [event_date - baseline_days_prior, event_date - (baseline_days_prior - 10)]
    baseline_start = dt - timedelta(days=baseline_days_prior)
    baseline_end = dt - timedelta(days=max(1, baseline_days_prior - 10))

    if hazard_type == "wildfire":
        pairing = {
            "sensor": "S2_OPTICAL",
            "mode": "MSI",
            "cloud_cover": "low",
            "change_detection_method": "nbr_diff",
        }
        crisis_label = "crisis_active_fire_window"
    elif hazard_type == "cyclone":
        pairing = {
            "sensor": "S1_SAR",
            "mode": "IW_GRDH",
            "relative_orbit": "descending",
            "polarization": "VV+VH",
            "change_detection_method": "coherence_loss",
        }
        crisis_label = "crisis_cyclone_window"
    elif hazard_type == "landslide":
        pairing = {
            "sensor": "S1_SAR",
            "mode": "IW_SLC",
            "relative_orbit": "descending",
            "polarization": "VV",
            "change_detection_method": "insar_coherence",
        }
        crisis_label = "crisis_landslide_window"
    else:
        # Default flood
        pairing = {
            "sensor": "S1_SAR",
            "mode": "IW_GRDH",
            "relative_orbit": "descending",
            "polarization": "VV+VH",
            "change_detection_method": "log_ratio_thresholding",
        }
        crisis_label = "crisis_inundation_window"

    return TemporalPlan(
        event_date=dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        baseline_window=TemporalWindow(
            start_date=baseline_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end_date=baseline_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            label="pre_event_baseline",
        ),
        crisis_window=TemporalWindow(
            start_date=crisis_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end_date=crisis_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            label=crisis_label,
        ),
        sensor_match_strategy="SAME_ORBIT_PASS",
        recommended_pairing=pairing,
    )
