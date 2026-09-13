"""
nodes/intent_extractor.py — NLP/heuristic intent extraction and mission planning node.
"""

from typing import Any, Dict, List, Optional, Tuple
from services.agent.schemas import PlanStep
from services.agent.security.sanitizer import sanitize_prompt
from services.agent.security.validator import validate_aoi_geometry, validate_intent
from pydantic import BaseModel, Field

_HAZARD_KEYWORDS = {
    "flood": ["flood", "inundation", "waterlogging", "submerged", "overflow", "river"],
    "wildfire": ["wildfire", "fire", "burn", "smoke", "hotspot"],
    "cyclone": ["cyclone", "hurricane", "typhoon", "storm"],
    "landslide": ["landslide", "mudslide", "slope failure"],
}

_SENSOR_PREFERENCES = {
    "flood": ["S1_SAR", "S2_OPTICAL"],
    "wildfire": ["S2_OPTICAL", "LANDSAT_8"],
    "cyclone": ["S1_SAR", "INSAT_3D"],
    "landslide": ["S1_SAR", "S2_OPTICAL", "CARTOSAT"],
}


def extract_intent_and_plan(
    query: str,
    aoi: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[PlanStep], List[str]]:
    """
    Parses a natural language mission prompt into structured intent, candidate sensors,
    and an ordered execution plan.
    """
    clean_query = sanitize_prompt(query)
    if aoi:
        validate_aoi_geometry(aoi)

    class IntentSchema(BaseModel):
        disaster_type: str = Field(
            description="The type of hazard detected (e.g., flood, wildfire)"
        )
        objectives: List[str] = Field(description="List of mission objectives")

    # In a real integration, this prompt is passed to an LLM.
    # llm_chain = prompt_template | llm | parser
    # intent_parsed = llm_chain.invoke({"query": clean_query})

    # We fallback to structured heuristics for testing if no LLM is provided:

    # Detect hazard type
    lower = clean_query.lower()
    detected_hazard = "flood"  # Default flagship mission
    for hazard, keywords in _HAZARD_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            detected_hazard = hazard
            break

    # Determine objectives
    objectives = []
    if any(w in lower for w in ["extent", "map", "area", "boundary"]):
        objectives.append("delineate_hazard_extent")
    if any(w in lower for w in ["damage", "building", "structure", "infrastructure", "impact"]):
        objectives.append("infrastructure_impact_assessment")
    if any(w in lower for w in ["trend", "history", "previous", "temporal", "baseline"]):
        objectives.append("temporal_change_detection")
    if not objectives:
        objectives.append("delineate_hazard_extent")

    intent = {
        "disaster_type": detected_hazard,
        "objectives": objectives,
        "raw_query": query,
        "sanitized_query": clean_query,
        "confidence_threshold": 0.70,
        "requires_multi_sensor": detected_hazard in ("flood", "landslide"),
    }
    validate_intent(intent)

    selected_sensors = _SENSOR_PREFERENCES.get(detected_hazard, ["S1_SAR", "S2_OPTICAL"])

    # Build plan DAG steps
    plan_steps = [
        PlanStep(
            step_id="step-1",
            name="temporal_planning",
            description="Compute pre-event baseline and crisis observation windows",
            tool="temporal_planner",
            parameters={"hazard_type": detected_hazard},
        ),
        PlanStep(
            step_id="step-2",
            name="search_observations",
            description="Query STAC/Bhoonidhi for available SAR and Optical scenes",
            tool="stac_search",
            parameters={"sensors": selected_sensors},
        ),
        PlanStep(
            step_id="step-3",
            name="sensor_arbitration",
            description="Arbitrate optimal sensor mode based on cloud cover & day/night conditions",
            tool="sensor_arbitrator",
            parameters={"priority": "balanced"},
        ),
        PlanStep(
            step_id="step-4",
            name="run_inference",
            description="Execute water detection / hazard segmentation models",
            tool="inference_executor",
            parameters={"hazard_type": detected_hazard},
        ),
        PlanStep(
            step_id="step-5",
            name="build_evidence_graph",
            description="Construct DAG of observations, inferences, and uncertainty factors",
            tool="evidence_builder",
            parameters={},
        ),
        PlanStep(
            step_id="step-6",
            name="confidence_gate",
            description="Evaluate composite confidence against uncertainty threshold",
            tool="confidence_evaluator",
            parameters={"min_confidence": 0.70},
        ),
        PlanStep(
            step_id="step-7",
            name="synthesize_output",
            description="Generate factual, evidence-grounded summary and WHY explanation",
            tool="evidence_synthesizer",
            parameters={},
        ),
    ]

    return intent, plan_steps, selected_sensors
