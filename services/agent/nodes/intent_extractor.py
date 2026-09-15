"""
nodes/intent_extractor.py — NLP/heuristic intent extraction and mission planning node.
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, SecretStr
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser

from services.agent.schemas import PlanStep
from services.agent.security.sanitizer import sanitize_prompt
from services.agent.security.validator import validate_aoi_geometry, validate_intent
from services.agent.config import get_agent_settings

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


class IntentSchema(BaseModel):
    disaster_type: str = Field(description="The type of hazard detected (e.g., flood, wildfire)")
    objectives: List[str] = Field(description="List of mission objectives")


def extract_intent_and_plan(
    query: str,
    aoi: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[PlanStep], List[str]]:
    """
    Parses a natural language mission prompt into structured intent, candidate sensors,
    and an ordered execution plan using LangChain and ChatOpenAI. Fallback to heuristics.
    """
    clean_query = sanitize_prompt(query)
    if aoi:
        validate_aoi_geometry(aoi)

    settings = get_agent_settings()
    intent_parsed = None

    if settings.openai_api_key:
        try:
            parser = PydanticOutputParser(pydantic_object=IntentSchema)
            prompt = PromptTemplate(
                template=(
                    "Extract the mission intent from the following query.\n"
                    "{format_instructions}\nQuery: {query}\n"
                ),
                input_variables=["query"],
                partial_variables={"format_instructions": parser.get_format_instructions()},
            )
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=SecretStr(settings.openai_api_key))
            llm_chain = prompt | llm | parser
            intent_parsed = llm_chain.invoke({"query": clean_query})
        except Exception as e:
            # Fallback to heuristics if LLM fails (e.g., network error, invalid key)
            import logging

            logging.getLogger(__name__).warning("LLM intent extraction failed: %s", e)
            intent_parsed = None

    if intent_parsed is None:
        # We fallback to structured heuristics for testing if no LLM is provided or it failed
        lower = clean_query.lower()
        detected_hazard = "flood"  # Default flagship mission
        for hazard, keywords in _HAZARD_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                detected_hazard = hazard
                break

        objectives = []
        if any(w in lower for w in ["extent", "map", "area", "boundary"]):
            objectives.append("delineate_hazard_extent")
        if any(w in lower for w in ["damage", "building", "structure", "infrastructure", "impact"]):
            objectives.append("infrastructure_impact_assessment")
        if any(w in lower for w in ["trend", "history", "previous", "temporal", "baseline"]):
            objectives.append("temporal_change_detection")
        if not objectives:
            objectives.append("delineate_hazard_extent")

        intent_parsed = IntentSchema(disaster_type=detected_hazard, objectives=objectives)

    intent = {
        "disaster_type": intent_parsed.disaster_type,
        "objectives": intent_parsed.objectives,
        "raw_query": query,
        "sanitized_query": clean_query,
        "confidence_threshold": 0.70,
        "requires_multi_sensor": intent_parsed.disaster_type in ("flood", "landslide"),
    }
    validate_intent(intent)

    selected_sensors = _SENSOR_PREFERENCES.get(
        intent_parsed.disaster_type, ["S1_SAR", "S2_OPTICAL"]
    )

    # Build plan DAG steps
    plan_steps = [
        PlanStep(
            step_id="step-1",
            name="temporal_planning",
            description="Compute pre-event baseline and crisis observation windows",
            tool="temporal_planner",
            parameters={"hazard_type": intent_parsed.disaster_type},
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
            parameters={"hazard_type": intent_parsed.disaster_type},
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
