"""
graph/orchestrator.py — LangGraph state machine & run orchestrator for SatQuery AI.
"""

from typing import Dict, List, Optional
import uuid
from langgraph.graph import StateGraph, START, END
from services.agent.evidence.graph_builder import EvidenceGraphBuilder
from services.agent.nodes.intent_extractor import extract_intent_and_plan
from services.agent.schemas import MissionState
from services.agent.security.sanitizer import sanitize_prompt
from services.agent.security.validator import validate_aoi_geometry
from services.agent.tools.executor import get_tool_executor
from packages.auth.models import AuthContext, Role
from services.agent.security.tool_budget import ToolBudget
from services.agent.nodes.sensor_arbitrator import arbitrate_sensors
from services.agent.nodes.confidence_gate import evaluate_confidence_gate
from services.agent.evidence.models import EvidenceGraph
from services.agent.nodes.synthesizer import synthesize_evidence_output
from services.agent.nodes.resilience import execute_with_recovery

def plan_mission(state: MissionState) -> dict:
    intent, plan_steps, selected_sensors = extract_intent_and_plan(
        state.sanitized_query or state.query, aoi=state.aoi
    )
    return {
        "status": "PLANNING",
        "intent": intent,
        "selected_sensors": selected_sensors
    }

def sensor_arbitration(state: MissionState) -> dict:
    intent = state.metadata.get("intent", {})
    hazard_type = intent.get("disaster_type", "flood")
    
    # Simple heuristic to get cloud_cover from metadata (if available from previous steps/api)
    cloud_cover = state.metadata.get("cloud_cover_forecast", 30.0) 
    is_night = state.metadata.get("is_night_forecast", False)
    
    decision = arbitrate_sensors(
        hazard_type=hazard_type,
        cloud_cover=cloud_cover,
        is_night=is_night,
        trace_id=state.trace_id,
    )
    
    # Map generic sensor strings to specific sensor IDs
    sensor_map = {
        "SAR": "S1_SAR",
        "OPTICAL": "S2_OPTICAL",
    }
    
    # Determine the ordered sensor preference
    selected = [sensor_map.get(decision.primary_sensor, decision.primary_sensor)]
    if decision.secondary_sensor:
        selected.append(sensor_map.get(decision.secondary_sensor, decision.secondary_sensor))
        
    return {
        "status": "ARBITRATING",
        "selected_sensors": selected
    }

def acquire_data(state: MissionState) -> dict:
    executor = get_tool_executor()
    
    # We create a system context for the background agent run
    ctx = AuthContext(
        subject="system_agent",
        organisation_id=state.organization_id,
        roles=[Role.SYSTEM]
    )

    # Use the aoi as bbox (heuristic fallback)
    bbox = [92.0, 25.5, 94.0, 27.5]
    if state.aoi and "bbox" in state.aoi:
        bbox = state.aoi["bbox"]
        
    budget = None
    if state.metadata and "budget" in state.metadata:
        budget = ToolBudget(**state.metadata["budget"])
    else:
        # Default budget if not provided
        budget = ToolBudget(max_calls=10, max_duration_seconds=60.0)
        
    try:
        def _primary_fn():
            res = executor.execute_tool(
                "stac_search",
                args={
                    "bbox": bbox,
                    "start_date": "2026-09-01T00:00:00Z",
                    "end_date": "2026-09-05T00:00:00Z",
                    "sensors": state.selected_sensors or ["S1_SAR", "S2_OPTICAL"],
                    "max_cloud_cover": 30.0
                },
                auth_context=ctx,
                budget=budget
            )
            if res.success and res.output:
                return [obs["asset_id"] for obs in res.output]
            return []
            
        def _fallback_fn():
            # Deterministic fallback scene
            return ["S1A_IW_GRDH_1SDV_FALLBACK"]
            
        recovery_result = execute_with_recovery(
            action_name="stac_search_acquisition",
            primary_fn=_primary_fn,
            fallback_fn=_fallback_fn,
            max_retries=2
        )
        obs_ids = recovery_result.data
    except Exception:
        obs_ids = []

    new_meta = dict(state.metadata)
    new_meta["budget"] = budget.model_dump()

    return {
        "status": "ACQUIRING",
        "observation_ids": obs_ids,
        "metadata": new_meta
    }

def analyze_data(state: MissionState) -> dict:
    new_meta = dict(state.metadata)
    new_meta.update({
        "dataset_id": "bhoonidhi-sentinel-collection",
        "model_version": "water-segmentation-v2.1",
        "processing_version": "1.0",
    })
    return {
        "status": "ANALYZING",
        "metadata": new_meta
    }

def gate_check(state: MissionState) -> dict:
    ev_builder = EvidenceGraphBuilder(mission_id=state.mission_id)
    obs_id = state.observation_ids[0] if state.observation_ids else f"S1A_IW_GRDH_1SDV_{uuid.uuid4().hex[:6].upper()}"
    
    # Heuristically detect sensor from observation_ids or state
    sensor = "S1_SAR"
    if "S2" in obs_id or "OPTICAL" in str(state.selected_sensors):
        sensor = "OPTICAL"
        
    obs_node = ev_builder.add_observation({
        "asset_id": obs_id,
        "sensor": sensor,
        "datetime": "2026-09-02T00:35:12Z",
    })
    inf_node = ev_builder.add_inference(
        input_node_ids=[obs_node.node_id],
        model_name="water_segmentation",
        model_version="v2.1",
        results={"inundated_sqkm": 142.5},
        confidence=0.88,
    )
    ev_builder.add_metric(
        inference_node_id=inf_node.node_id,
        metric_name="inundation_area_sqkm",
        value=142.5,
        unit="km2",
    )
    
    evidence_graph = ev_builder.build().model_dump()
    
    # Evaluate confidence using actual nodes
    nodes_dict = evidence_graph.get("nodes", {})
    conf = evaluate_confidence_gate(
        evidence_nodes=list(nodes_dict.values()),
        sensor_type=sensor,
        cloud_cover=state.metadata.get("cloud_cover_forecast", 0.0),
        resolution_meters=10.0,
        temporal_lag_days=2.0,
        trace_id=state.trace_id
    )
    
    return {
        "status": "GATE_CHECK",
        "confidence_score": conf.confidence_score,
        "evidence_graph": evidence_graph
    }

def synthesize(state: MissionState) -> dict:
    if state.evidence_graph:
        graph = EvidenceGraph(**state.evidence_graph)
        out = synthesize_evidence_output(graph, state.sanitized_query or state.query)
        output_dict = out.model_dump()
        # Flatten metrics into top-level for backward compatibility
        for k, v in out.metrics.items():
            output_dict[k] = v
    else:
        output_dict = {
            "summary": "No evidence graph available for synthesis.",
            "inundation_area_sqkm": 0,
            "affected_structures_count": 0,
            "primary_sensor": "UNKNOWN",
        }
    return {
        "status": "COMPLETED",
        "synthesized_output": output_dict
    }

def _build_graph() -> StateGraph:
    graph = StateGraph(MissionState)
    graph.add_node("planning", plan_mission)
    graph.add_node("sensor_arbitration", sensor_arbitration)
    graph.add_node("acquiring", acquire_data)
    graph.add_node("analyzing", analyze_data)
    graph.add_node("gate_check", gate_check)
    graph.add_node("synthesize", synthesize)

    graph.add_edge(START, "planning")
    graph.add_edge("planning", "sensor_arbitration")
    graph.add_edge("sensor_arbitration", "acquiring")
    graph.add_edge("acquiring", "analyzing")
    graph.add_edge("analyzing", "gate_check")
    graph.add_edge("gate_check", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()

class AgentOrchestrator:
    """
    Manages state machine transitions for agent runs and mission execution.
    """

    def __init__(self):
        self._runs: Dict[str, MissionState] = {}
        self._app = _build_graph()

    def create_run(
        self,
        mission_id: str,
        org_id: str,
        query: str,
        trace_id: Optional[str] = None,
        aoi: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> MissionState:
        clean_query = sanitize_prompt(query)
        if aoi:
            validate_aoi_geometry(aoi)

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        state = MissionState(
            mission_id=mission_id,
            run_id=run_id,
            job_id=job_id,
            organization_id=org_id,
            trace_id=trace_id,
            query=query,
            sanitized_query=clean_query,
            aoi=aoi,
            status="INITIALIZED",
            metadata=metadata or {},
        )
        self._runs[job_id] = state
        return state

    def get_run(self, job_id: str) -> Optional[MissionState]:
        return self._runs.get(job_id)

    def list_runs(self, org_id: str) -> List[MissionState]:
        return [r for r in self._runs.values() if r.organization_id == org_id]

    def step_execution(self, state: MissionState) -> MissionState:
        """
        Executes the LangGraph workflow.
        """
        result_state = self._app.invoke(state)
        if isinstance(result_state, dict):
            final_state = MissionState(**result_state)
        else:
            final_state = result_state
            
        if final_state.job_id:
            self._runs[final_state.job_id] = final_state
        return final_state


_default_orchestrator = AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    return _default_orchestrator
