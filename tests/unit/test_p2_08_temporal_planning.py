"""
tests/unit/test_p2_08_temporal_planning.py
Unit tests for P2-08: Temporal planning and previous/current selection.
"""

import pytest
from nodes.temporal_planner import compute_temporal_plan


@pytest.mark.unit
def test_temporal_planning_and_previous_current_selection_valid():
    """Valid event date produces distinct baseline and crisis windows with orbit matching."""
    plan = compute_temporal_plan(
        event_date_str="2026-09-02T12:00:00Z",
        baseline_days_prior=25,
        crisis_window_days=6,
    )
    assert plan.event_date == "2026-09-02T12:00:00Z"
    assert plan.baseline_window.label == "pre_event_baseline"
    assert plan.crisis_window.label == "crisis_inundation_window"
    assert plan.baseline_window.end_date < plan.crisis_window.start_date
    assert plan.sensor_match_strategy == "SAME_ORBIT_PASS"
    assert plan.recommended_pairing["sensor"] == "S1_SAR"


@pytest.mark.unit
def test_temporal_planning_and_previous_current_selection_invalid_input():
    """Malformed date format and negative windows raise ValueError."""
    # Invalid date string
    with pytest.raises(ValueError, match="Invalid event date format"):
        compute_temporal_plan(event_date_str="not-a-valid-date")

    # Negative baseline window
    with pytest.raises(ValueError, match="baseline_days_prior must be positive"):
        compute_temporal_plan(
            event_date_str="2026-09-02",
            baseline_days_prior=-5,
        )

    # Negative crisis window
    with pytest.raises(ValueError, match="crisis_window_days must be positive"):
        compute_temporal_plan(
            event_date_str="2026-09-02",
            crisis_window_days=0,
        )
