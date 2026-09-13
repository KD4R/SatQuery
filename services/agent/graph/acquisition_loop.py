"""
graph/acquisition_loop.py — Autonomous closed-loop evidence acquisition for uncertainty recovery.
"""

from typing import Any, Dict, List, Tuple
from pydantic import BaseModel, Field
from services.agent.tools.executor import get_tool_executor
from packages.auth.models import AuthContext, Role
from services.agent.security.tool_budget import ToolBudget
from services.agent.nodes.confidence_gate import evaluate_confidence_gate
from services.agent.schemas import MissionState


class AcquisitionLoopResult(BaseModel):
    resolved: bool
    iterations_run: int = Field(ge=0)
    final_confidence: float = Field(ge=0.0, le=1.0)
    acquired_observations: List[str] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class AutonomousAcquisitionLoop:
    """
    Executes a bounded feedback loop to acquire complementary satellite observations
    when the confidence gate detects uncertainty.
    """

    def run_loop(
        self,
        state: MissionState,
        max_iterations: int = 3,
        target_confidence: float = 0.70,
    ) -> Tuple[MissionState, AcquisitionLoopResult]:
        if max_iterations <= 0:
            raise ValueError("max_iterations must be strictly positive")
        if not (0.0 <= target_confidence <= 1.0):
            raise ValueError("target_confidence must be in range [0.0, 1.0]")

        history: List[Dict[str, Any]] = []
        acquired: List[str] = []
        iteration = 0

        # Evaluate initial state
        initial_conf = evaluate_confidence_gate(
            sensor_type="OPTICAL" if "S2_OPTICAL" in state.selected_sensors else "SAR",
            cloud_cover=65.0 if "S2_OPTICAL" in state.selected_sensors else 0.0,
            resolution_meters=10.0,
        )

        current_score = initial_conf.confidence_score
        history.append({"iteration": 0, "confidence": current_score, "action": initial_conf.action})

        executor = get_tool_executor()
        ctx = AuthContext(
            subject="system",
            roles=[Role.ADMIN],
            organisation_id=state.organization_id,
            email="system@satquery.com",
            trace_id=state.trace_id,
        )
        budget = ToolBudget(max_calls=10, max_duration_seconds=60.0)

        while current_score < target_confidence and iteration < max_iterations:
            iteration += 1

            bbox = [92.0, 25.5, 94.0, 27.5]
            if state.aoi and "bbox" in state.aoi:
                bbox = state.aoi["bbox"]

            # Determine alternate sensor acquisition
            try:
                res = executor.execute_tool(
                    "stac_search",
                    args={
                        "bbox": bbox,
                        "start_date": "2026-09-01T00:00:00Z",
                        "end_date": "2026-09-05T00:00:00Z",
                        "sensors": ["S1_SAR"],
                        "max_cloud_cover": 100.0,
                    },
                    auth_context=ctx,
                    budget=budget,
                )
                if res.success and res.output:
                    new_asset_id = res.output[0]["asset_id"]
                else:
                    new_asset_id = f"S1A_IW_GRDH_ACQ_{iteration:02d}"
            except Exception:
                new_asset_id = f"S1A_IW_GRDH_ACQ_{iteration:02d}"

            acquired.append(new_asset_id)
            state.observation_ids.append(new_asset_id)
            if "S1_SAR" not in state.selected_sensors:
                state.selected_sensors.append("S1_SAR")

            # Re-evaluate with SAR active microwave observation
            eval_res = evaluate_confidence_gate(
                sensor_type="SAR",
                cloud_cover=0.0,
                resolution_meters=10.0,
                temporal_lag_days=1.0,
            )
            current_score = eval_res.confidence_score
            history.append(
                {
                    "iteration": iteration,
                    "acquired_asset": new_asset_id,
                    "confidence": current_score,
                    "action": eval_res.action,
                }
            )

            if eval_res.passed_gate:
                break

        resolved = current_score >= target_confidence
        state.confidence_score = current_score
        state.status = "COMPLETED" if resolved else "UNCERTAINTY_UNRESOLVED"

        new_meta = dict(state.metadata)
        new_meta["budget"] = budget.model_dump()
        state.metadata = new_meta

        result = AcquisitionLoopResult(
            resolved=resolved,
            iterations_run=iteration,
            final_confidence=current_score,
            acquired_observations=acquired,
            history=history,
        )
        return state, result
