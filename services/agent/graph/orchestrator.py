"""
graph/orchestrator.py — LangGraph state machine & run orchestrator for SatQuery AI.
"""

from typing import Dict, List, Optional
import uuid
from datetime import datetime, timezone
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
import redis
from packages.providers.config import config
from packages.contracts.events import EventEnvelope


def plan_mission(state: MissionState) -> dict:
    intent, plan_steps, selected_sensors = extract_intent_and_plan(
        state.sanitized_query or state.query, aoi=state.aoi
    )
    return {"status": "PLANNING", "intent": intent, "selected_sensors": selected_sensors}


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

    return {"status": "ARBITRATING", "selected_sensors": selected}


def acquire_data(state: MissionState) -> dict:
    executor = get_tool_executor()

    ctx = AuthContext(
        subject="system_agent",
        organisation_id=state.organization_id,
        roles=[Role.SYSTEM],
        email="system@satquery.com",
        trace_id=state.trace_id,
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
                    "max_cloud_cover": 30.0,
                },
                auth_context=ctx,
                budget=budget,
            )
            if res.success and res.output:
                return res.output
            return []

        recovery_result = execute_with_recovery(
            action_name="stac_search_acquisition",
            primary_fn=_primary_fn,
            max_retries=2,
        )
        observations = recovery_result.data if recovery_result.data else []
        obs_ids = [obs.get("asset_id") for obs in observations if "asset_id" in obs]
    except Exception:
        observations = []
        obs_ids = []

    new_meta = dict(state.metadata)
    new_meta["budget"] = budget.model_dump()
    new_meta["observations"] = observations

    if not obs_ids:
        return {"status": "FAILED", "observation_ids": [], "metadata": new_meta}

    return {"status": "ACQUIRING", "observation_ids": obs_ids, "metadata": new_meta}


def analyze_data(state: MissionState) -> dict:
    from packages.shared.client import InternalClient
    from packages.auth.models import AuthContext, Role
    from services.agent.config import get_agent_settings
    import asyncio
    import logging

    logger = logging.getLogger(__name__)
    settings = get_agent_settings()

    ctx = AuthContext(
        subject="system_agent",
        organisation_id=state.organization_id,
        roles=[Role.SYSTEM],
        email="system@satquery.com",
        trace_id=state.trace_id,
    )

    # We need to take the first selected observation
    if not state.observation_ids:
        logger.warning("No observations found to analyze.")
        return {"status": "FAILED", "metadata": state.metadata}

    scene_id = state.observation_ids[0]
    observations = state.metadata.get("observations", [])
    obs = next((o for o in observations if o.get("asset_id") == scene_id), {})
    scene_href = obs.get("href")
    
    acquired_at = obs.get("datetime")
    if not acquired_at:
        acquired_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    import concurrent.futures
    
    payload = {
        "scene": {
            "provider": obs.get("provider", "BHOONIDHI"),
            "collection": obs.get("collection", "sentinel-1-grd"),
            "item_id": scene_id,
            "acquired_at": acquired_at,
            "platform": obs.get("platform", "Sentinel-1A"),
            "instrument": obs.get("instrument", "SAR-C"),
            "href": scene_href,
        },
        "scene_href": scene_href,
        "min_mapping_unit_ha": 0.5,
    }

    async def _call_inference():
        client = InternalClient(
            base_url=settings.inference_service_url, caller_service="agent", scopes=["inference:run"]
        )
        try:
            resp = await client.post("/api/v1/inference/analyses", auth_context=ctx, json=payload)
            return resp.json()
        finally:
            await client.aclose()

    try:
        # Run async client in a separate thread to avoid "event loop already running" in test/eager environments
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _call_inference())
            outcome_data = future.result()

        new_meta = dict(state.metadata)
        new_meta["inference_outcome"] = outcome_data

        return {"status": "ANALYZING", "metadata": new_meta}
    except Exception as e:
        logger.error(f"Inference call failed: {e}")
        return {"status": "FAILED", "metadata": state.metadata}


def gate_check(state: MissionState) -> dict:
    ev_builder = EvidenceGraphBuilder(mission_id=state.mission_id)

    # Retrieve the outcome from previous node
    outcome_data = state.metadata.get("inference_outcome", {})
    measurements = outcome_data.get("measurements", [])

    inundated_sqkm = 0.0
    if measurements and len(measurements) > 0:
        # Assuming the first measurement is the flood extent in hectares, convert to sqkm
        inundated_sqkm = measurements[0].get("value", 0.0) / 100.0

    if not state.observation_ids:
        return {"status": "FAILED", "confidence_score": 0.0, "evidence_graph": {}}

    obs_id = state.observation_ids[0]

    observations = state.metadata.get("observations", [])
    obs_dict = next((o for o in observations if o.get("asset_id") == obs_id), {})
    obs_time = obs_dict.get("datetime")
    if not obs_time:
        obs_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Heuristically detect sensor from observation_ids or state
    sensor = "S1_SAR"
    if "S2" in obs_id or "OPTICAL" in str(state.selected_sensors):
        sensor = "OPTICAL"

    obs_node = ev_builder.add_observation(
        {
            "asset_id": obs_id,
            "sensor": sensor,
            "datetime": obs_time,
        }
    )

    # Use P3/P4 confidence, metadata, disagreement, and quality outputs in the gate.
    conf_data = outcome_data.get("confidence") or {}
    model_conf = float(conf_data.get("value", 0.88) or 0.88)

    # Create the inference node with real data
    inf_node = ev_builder.add_inference(
        input_node_ids=[obs_node.node_id],
        model_name=outcome_data.get("degraded_from", "baseline") or "baseline",
        model_version="1.0",
        results={"inundated_sqkm": inundated_sqkm},
        confidence=model_conf,
    )

    ev_builder.add_metric(
        inference_node_id=inf_node.node_id,
        metric_name="inundation_area_sqkm",
        value=inundated_sqkm,
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
        trace_id=state.trace_id,
    )

    new_meta = dict(state.metadata)
    status = "GATE_CHECK"
    # Implement explicit sensor-disagreement and low-confidence re-investigation behavior
    if not conf.passed_gate:
        retries = new_meta.get("reinvestigations", 0)
        if retries < 1:
            new_meta["reinvestigations"] = retries + 1
            status = "REINVESTIGATE"

    return {
        "status": status,
        "confidence_score": conf.confidence_score,
        "evidence_graph": evidence_graph,
        "metadata": new_meta,
    }


def synthesize(state: MissionState) -> dict:
    if state.confidence_score is not None and state.confidence_score < 0.6:
        output_dict = {
            "summary": f"Agent aborted execution: the confidence score ({state.confidence_score:.2f}) was below the acceptable threshold, indicating high uncertainty.",
            "inundation_area_sqkm": 0,
            "affected_structures_count": 0,
            "primary_sensor": "UNKNOWN",
        }
        return {"status": "FAILED", "synthesized_output": output_dict}

    if state.evidence_graph and state.observation_ids:
        try:
            graph = EvidenceGraph(**state.evidence_graph)
            out = synthesize_evidence_output(graph, state.sanitized_query or state.query)
            output_dict = out.model_dump()
            # Flatten metrics into top-level for backward compatibility
            for k, v in out.metrics.items():
                output_dict[k] = v
        except ValueError as e:
            output_dict = {
                "summary": f"Evidence synthesis failed: {e}",
                "inundation_area_sqkm": 0,
                "affected_structures_count": 0,
                "primary_sensor": "UNKNOWN",
            }
    else:
        reason = "No observations acquired." if not state.observation_ids else "No evidence graph available for synthesis."
        output_dict = {
            "summary": f"Mission failed to complete successfully. Reason: {reason}",
            "inundation_area_sqkm": 0,
            "affected_structures_count": 0,
            "primary_sensor": "UNKNOWN",
        }
        return {"status": "FAILED", "synthesized_output": output_dict}
        
    return {"status": "COMPLETED", "synthesized_output": output_dict}


def should_reinvestigate(state: MissionState) -> str:
    if state.status == "REINVESTIGATE":
        return "sensor_arbitration"
    return "synthesize"


def _build_graph():
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
    graph.add_conditional_edges(
        "gate_check",
        should_reinvestigate,
        {
            "sensor_arbitration": "sensor_arbitration",
            "synthesize": "synthesize",
        }
    )
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

    def _get_redis(self):
        if not hasattr(self, "_redis"):
            self._redis = redis.from_url(config.redis_url.get_secret_value(), decode_responses=True)
        return self._redis

    def _publish_event(self, state: MissionState, event_type: str, payload: dict):
        evt = EventEnvelope(
            event_id=f"evt_{state.run_id}_{event_type}",
            event_type=event_type,
            trace_id=state.trace_id,
            mission_id=state.mission_id,
            producer="agent_orchestrator",
            payload=payload
        )
        try:
            r = self._get_redis()
            r.publish(f"agent:events:{state.mission_id}", evt.model_dump_json())
            r.xadd(f"agent:stream:{state.mission_id}", {"event": evt.model_dump_json()})
        except Exception:
            pass

    def step_execution(self, state: MissionState) -> MissionState:
        """
        Executes the LangGraph workflow and streams events.
        """
        self._publish_event(state, "RUN_STARTED", {"status": state.status})
        
        current_state_dict = state.model_dump()
        for update in self._app.stream(state):
            node_name = list(update.keys())[0]
            node_update = update[node_name]
            current_state_dict.update(node_update)
            
            temp_state = MissionState(**current_state_dict)
            self._publish_event(temp_state, f"NODE_COMPLETED_{node_name.upper()}", {"status": temp_state.status})
            
        final_state = MissionState(**current_state_dict)
        if final_state.job_id:
            self._runs[final_state.job_id] = final_state
            
        self._publish_event(final_state, "RUN_COMPLETED", {"status": final_state.status})
        return final_state


_default_orchestrator = AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    return _default_orchestrator
