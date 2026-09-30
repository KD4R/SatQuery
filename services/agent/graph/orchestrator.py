"""
graph/orchestrator.py — LangGraph state machine & run orchestrator for SatQuery AI.
"""

import logging
import os
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timedelta, timezone
from langgraph.graph import StateGraph, START, END
from services.agent.evidence.graph_builder import EvidenceGraphBuilder
from services.agent.nodes.intent_extractor import extract_intent_and_plan
from services.agent.schemas import MissionState
from services.agent.security.sanitizer import sanitize_prompt
from services.agent.security.validator import validate_aoi_geometry
from services.agent.tools.executor import get_tool_executor
from packages.auth.models import AuthContext, Role
from services.agent.events import (
    emit_acquiring_evidence,
    emit_agent_thought,
    emit_sensor_agreement,
    emit_sensor_disagreement,
)
from services.agent.security.tool_budget import ToolBudget
from services.agent.nodes.sensor_arbitrator import arbitrate_sensors
from services.agent.nodes.confidence_gate import evaluate_confidence_gate
from services.agent.evidence.models import EvidenceGraph
from services.agent.nodes.synthesizer import synthesize_evidence_output
from services.agent.nodes.resilience import execute_with_recovery
from services.agent.graph.run_inputs import (
    AOIError,
    _parse_instant,
    aoi_bbox,
    aoi_geometry,
    bbox_area_km2,
    coverage_fraction,
    geometry_bbox,
    iso_z,
    rank_sar_scenes,
    requested_window,
    sensor_of,
)
import redis
from packages.providers.config import config
from packages.contracts.events import EventEnvelope

logger = logging.getLogger(__name__)


def _geometry_bbox(geometry: dict | None) -> list[float] | None:
    """Return the WGS84 bbox of a GeoJSON geometry (kept for existing callers)."""
    return geometry_bbox(geometry)


def _build_inference_scene(scene_info: dict, scene_id: str, scene_href: str, acquired_at: str) -> dict:
    """Build the strict ``SceneRef`` payload expected by the inference API."""
    provider = scene_info.get("provider") or "planetary_computer"
    if hasattr(provider, "value"):
        provider = provider.value
    provider = str(provider).lower()
    allowed_providers = {
        "asf_hyp3", "copernicus_dataspace", "planetary_computer", "bhoonidhi",
        "sen1floods11", "senforflood",
    }
    if provider not in allowed_providers:
        provider = "planetary_computer"

    pass_direction = scene_info.get("pass_direction")
    if hasattr(pass_direction, "value"):
        pass_direction = pass_direction.value
    if pass_direction not in {None, "ASCENDING", "DESCENDING"}:
        pass_direction = None

    relative_orbit = scene_info.get("relative_orbit")
    try:
        relative_orbit = int(relative_orbit) if relative_orbit is not None else None
    except (TypeError, ValueError):
        relative_orbit = None

    return {
        "provider": provider,
        "collection": str(scene_info.get("collection") or "sentinel-1-rtc"),
        "item_id": str(scene_info.get("item_id") or scene_id),
        "acquired_at": acquired_at,
        "platform": str(scene_info.get("platform") or "SENTINEL-1A"),
        "instrument": str(scene_info.get("instrument") or "C-SAR"),
        "relative_orbit": relative_orbit,
        "pass_direction": pass_direction,
        "href": scene_href,
        "cloud_cover": scene_info.get("cloud_cover"),
    }


def _intent(state: MissionState) -> dict:
    """The extracted intent. ``plan_mission`` writes it to ``state.intent``; older
    runs stored it under ``metadata["intent"]``, which is still honoured."""
    return state.intent or state.metadata.get("intent") or {}


def _selected_observation(state: MissionState) -> dict:
    """The observation this run analyses (chosen in ``acquire_data``)."""
    observations = state.metadata.get("observations", [])
    wanted = state.metadata.get("selected_observation_id") or (
        state.observation_ids[0] if state.observation_ids else None
    )
    return next((o for o in observations if o.get("observation_id") == wanted), {})


def _as_float(value) -> Optional[float]:
    """Decimal / numeric string / number -> float; None stays None.

    The inference API serialises Decimal fields (measurement values, confidence)
    as JSON strings, so arithmetic on the raw value raises TypeError.
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


#: Ground resolution of the Planetary Computer ``sentinel-1-rtc`` product (10 m
#: pixel spacing, per the collection's documentation). Used only when the item
#: itself does not state a resolution.
_S1_RTC_RESOLUTION_M = 10.0


def plan_mission(state: MissionState) -> dict:
    intent, plan_steps, selected_sensors = extract_intent_and_plan(
        state.sanitized_query or state.query, aoi=state.aoi
    )
    return {"status": "PLANNING", "intent": intent, "selected_sensors": selected_sensors}


def sensor_arbitration(state: MissionState) -> dict:
    intent = _intent(state)
    hazard_type = str(intent.get("disaster_type", "flood")).lower()

    # A cloud forecast is only used when a caller actually supplied one. There is
    # no forecast provider wired in, and inventing a figure here used to produce
    # rationales such as "cloud cover at 30.0% exceeds ..." that nobody measured.
    forecast = _as_float(state.metadata.get("cloud_cover_forecast"))
    is_night = bool(state.metadata.get("is_night_forecast", False))

    decision_meta: dict = {"cloud_cover_forecast": forecast}
    if hazard_type in ("flood", "inundation"):
        # The only validated live model is Sentinel-1 (VV+VH) water segmentation,
        # so the search is for SAR regardless of weather. Optical would be found
        # and then could not be analysed.
        selected = ["S1_SAR"]
        rationale = (
            "Live flood inference is validated for Sentinel-1 SAR (VV+VH) only; "
            "C-band SAR also images through cloud, which matters during floods."
        )
        if forecast is not None:
            rationale += f" Supplied cloud forecast: {forecast:.0f}%."
        decision_meta.update(primary="S1_SAR", secondary=None, rationale=rationale)
    elif forecast is not None or is_night:
        decision = arbitrate_sensors(
            hazard_type=hazard_type,
            cloud_cover=forecast if forecast is not None else 0.0,
            is_night=is_night,
            trace_id=state.trace_id,
        )
        sensor_map = {"SAR": "S1_SAR", "OPTICAL": "S2_OPTICAL"}
        selected = [sensor_map.get(decision.primary_sensor, decision.primary_sensor)]
        if decision.secondary_sensor:
            selected.append(sensor_map.get(decision.secondary_sensor, decision.secondary_sensor))
        decision_meta.update(
            primary=selected[0],
            secondary=selected[1] if len(selected) > 1 else None,
            rationale=decision.rationale,
        )
    else:
        selected = list(state.selected_sensors or ["S1_SAR"])
        decision_meta.update(
            primary=selected[0],
            secondary=selected[1] if len(selected) > 1 else None,
            rationale=(
                f"No cloud forecast was supplied; using the default sensor preference "
                f"for {hazard_type}."
            ),
        )

    # Live agent events (P5 §2C). Emission is fire-and-forget; it must never
    # fail the run.
    if len(selected) > 1:
        emit_sensor_disagreement(state.mission_id, state.trace_id, None, selected[0], selected[1])
    else:
        emit_sensor_agreement(state.mission_id, state.trace_id, selected[0])

    new_meta = dict(state.metadata)
    new_meta["sensor_decision"] = decision_meta
    return {"status": "ARBITRATING", "selected_sensors": selected, "metadata": new_meta}


def acquire_data(state: MissionState) -> dict:
    executor = get_tool_executor()

    ctx = AuthContext(
        subject="system_agent",
        organisation_id=state.organization_id,
        roles=[Role.SYSTEM],
        email="system@satquery.com",
        trace_id=state.trace_id,
    )

    new_meta = dict(state.metadata)
    fixture = state.metadata.get("demo_fixture")

    # ── Reinvestigation: analyse the next-best scene, never the same one twice ──
    analysed = list(state.metadata.get("analysed_observation_ids", []))
    if (
        state.metadata.get("reinvestigations")
        and state.metadata.get("observations")
        and not fixture
    ):
        try:
            box = aoi_bbox(state.aoi)
        except AOIError:
            box = None
        ranked = (
            rank_sar_scenes(state.metadata["observations"], box, exclude=analysed) if box else []
        )
        if ranked:
            chosen = ranked[0]
            new_meta["selected_observation_id"] = chosen["observation_id"]
            new_meta["reinvestigation_exhausted"] = False
            ids = [chosen["observation_id"]] + [o["observation_id"] for o in ranked[1:]]
            emit_agent_thought(
                state.mission_id,
                state.trace_id,
                "acquiring",
                "Confidence was low; analysing the next-best Sentinel-1 scene.",
            )
            return {"status": "ACQUIRING", "observation_ids": ids, "metadata": new_meta}
        new_meta["reinvestigation_exhausted"] = True
        return {"status": "ACQUIRING", "metadata": new_meta}

    # ── AOI: the user's, or nothing. No default location. ──
    if not fixture:
        try:
            bbox = aoi_bbox(state.aoi)
        except AOIError as exc:
            new_meta["acquisition_error"] = {"reason": "AOI_REQUIRED", "explanation": str(exc)}
            new_meta["observations"] = []
            emit_agent_thought(
                state.mission_id,
                state.trace_id,
                "acquiring",
                "No usable area of interest was supplied; the run cannot search imagery.",
            )
            return {"status": "FAILED", "observation_ids": [], "metadata": new_meta}
        area_km2 = bbox_area_km2(bbox)
        max_km2 = float(os.getenv("AGENT_MAX_AOI_KM2", "2500"))
        if area_km2 > max_km2:
            new_meta["acquisition_error"] = {
                "reason": "AOI_TOO_LARGE",
                "explanation": (
                    f"The AOI covers about {area_km2:,.0f} km²; live analysis is limited "
                    f"to {max_km2:,.0f} km² per run. Draw a smaller area."
                ),
            }
            new_meta["observations"] = []
            return {"status": "FAILED", "observation_ids": [], "metadata": new_meta}
    else:
        bbox = None

    # ── Time window: the caller's, else the last 90 days, widened once to 365 ──
    try:
        window = requested_window(state.temporal_window)
    except ValueError as exc:
        new_meta["acquisition_error"] = {
            "reason": "INVALID_TEMPORAL_WINDOW",
            "explanation": str(exc),
        }
        new_meta["observations"] = []
        return {"status": "FAILED", "observation_ids": [], "metadata": new_meta}

    budget = None
    if state.metadata and state.metadata.get("budget"):
        budget = ToolBudget(**state.metadata["budget"])
    else:
        budget = ToolBudget(max_calls=10, max_duration_seconds=60.0)

    sensors = state.selected_sensors or ["S1_SAR"]
    search_log: List[dict] = []

    def _search(start: datetime, end: datetime) -> list:
        res = executor.execute_tool(
            "stac_search",
            args={
                "bbox": bbox,
                "start_date": iso_z(start),
                "end_date": iso_z(end),
                "sensors": sensors,
                "max_cloud_cover": 30.0,
            },
            auth_context=ctx,
            budget=budget,
        )
        found = res.output if (res.success and res.output) else []
        search_log.append(
            {
                "start": iso_z(start),
                "end": iso_z(end),
                "results": len(found),
                "error": (
                    None
                    if res.success
                    else (
                        getattr(res, "error", None)
                        or (getattr(res, "metadata", None) or {}).get("error")
                        or "search failed"
                    )
                ),
            }
        )
        return found

    try:
        def _primary_fn():
            if fixture:
                return [
                    {
                        "observation_id": item["asset_id"],
                        "scene": {
                            "provider": "planetary_computer",
                            "collection": "sentinel-1-rtc" if item.get("sensor") == "S1_SAR" else "sentinel-2-l2a",
                            "item_id": item["asset_id"],
                            "acquired_at": fixture["temporal_window"]["event_date"],
                            "platform": "Sentinel-1A" if item.get("sensor") == "S1_SAR" else "Sentinel-2A",
                            "instrument": "C-SAR" if item.get("sensor") == "S1_SAR" else "MSI",
                            "relative_orbit": None,
                            "pass_direction": None,
                            "href": "demo://pinned-flood-scene",
                            "cloud_cover": item.get("cloud_cover"),
                        },
                        "assets": {},
                    }
                    for item in fixture.get("observations", [])
                ]
            if window is not None:
                # The caller asked for this period; widening it would answer a
                # different question, so an empty result is reported as such.
                return _search(*window)
            now = datetime.now(timezone.utc)
            results = _search(now - timedelta(days=90), now)
            if not results:
                logger.info("No STAC results in the last 90 days; widening to 365 days")
                results = _search(now - timedelta(days=365), now)
            return results

        recovery_result = execute_with_recovery(
            action_name="stac_search_acquisition",
            primary_fn=_primary_fn,
            fallback_fn=lambda: [],
            max_retries=2,
        )
        observations = recovery_result.data if recovery_result.data else []
    except Exception:
        logger.exception("STAC acquisition failed")
        observations = []

    emit_acquiring_evidence(
        state.mission_id,
        state.trace_id,
        "Selecting the observations that cover the area of interest.",
        sensors=sensors,
    )

    # What was actually searched, so the UI can show it rather than assume it.
    new_meta["search"] = {
        "bbox": bbox,
        "sensors": sensors,
        "requested_window": (
            {"start": iso_z(window[0]), "end": iso_z(window[1])} if window else None
        ),
        "attempts": search_log,
        "widened": window is None and len(search_log) > 1,
    }
    new_meta["budget"] = budget.model_dump()
    new_meta["observations"] = observations

    if fixture:
        obs_ids = [o["observation_id"] for o in observations]
        if obs_ids:
            new_meta["selected_observation_id"] = obs_ids[0]
    else:
        ranked = rank_sar_scenes(observations, bbox)
        obs_ids = [o["observation_id"] for o in ranked]
        if ranked:
            new_meta["selected_observation_id"] = ranked[0]["observation_id"]
            new_meta["selected_scene_coverage"] = round(
                coverage_fraction(bbox, geometry_bbox(ranked[0].get("geometry"))), 3
            )

    if not obs_ids:
        if observations:
            reason, text = (
                "NO_ANALYSABLE_SCENE",
                f"{len(observations)} scene(s) were found but none is a Sentinel-1 "
                "scene with both VV and VH bands, which live flood inference requires.",
            )
        elif any(a.get("error") for a in search_log):
            reason, text = "CATALOGUE_UNAVAILABLE", "The satellite catalogue search failed."
        else:
            span = new_meta["search"]["requested_window"] or (
                {"start": search_log[-1]["start"], "end": search_log[-1]["end"]}
                if search_log
                else None
            )
            reason = "NO_SCENES_IN_WINDOW"
            text = (
                f"No scenes intersect the AOI between {span['start']} and {span['end']}."
                if span
                else "No scenes intersect the AOI."
            )
        new_meta["acquisition_error"] = {"reason": reason, "explanation": text}
        emit_agent_thought(
            state.mission_id,
            state.trace_id,
            "acquiring",
            "No usable observations were returned; the run cannot proceed.",
        )
        return {"status": "FAILED", "observation_ids": [], "metadata": new_meta}

    emit_agent_thought(
        state.mission_id,
        state.trace_id,
        "acquiring",
        f"{len(obs_ids)} analysable observation(s) returned for the AOI.",
    )
    return {"status": "ACQUIRING", "observation_ids": obs_ids, "metadata": new_meta}


def _inference_timeout_s() -> float:
    return float(os.getenv("AGENT_INFERENCE_TIMEOUT_S", "180"))


def analyze_data(state: MissionState) -> dict:
    from packages.shared.client import InternalClient
    from services.agent.config import get_agent_settings
    import asyncio
    import concurrent.futures

    settings = get_agent_settings()
    new_meta = dict(state.metadata)

    if state.metadata.get("acquisition_error"):
        # Nothing to analyse; the acquisition failure is the run's answer.
        return {"status": "FAILED", "metadata": new_meta}

    if state.metadata.get("reinvestigation_exhausted"):
        # Reinvestigation found no other scene: keep the first analysis as-is.
        return {"status": "ANALYZING", "metadata": new_meta}

    hazard_type = str(_intent(state).get("disaster_type", "flood")).lower()
    if hazard_type not in {"flood", "inundation"}:
        new_meta["inference_outcome"] = {
            "outcome": "abstained",
            "reason": "UNSUPPORTED_HAZARD_MODEL",
            "explanation": f"No validated live inference model is registered for hazard '{hazard_type}'.",
        }
        return {"status": "FAILED", "metadata": new_meta}

    ctx = AuthContext(
        subject="system_agent",
        organisation_id=state.organization_id,
        roles=[Role.SYSTEM],
        email="system@satquery.com",
        trace_id=state.trace_id,
    )

    if not state.observation_ids:
        logger.warning("No observations found to analyze.")
        return {"status": "FAILED", "metadata": new_meta}

    obs = _selected_observation(state)
    scene_id = obs.get("observation_id") or state.observation_ids[0]

    fixture = state.metadata.get("demo_fixture")
    if fixture:
        result = fixture["inferences"]
        area_ha = float(result["inundation_area_sqkm"]) * 100.0
        new_meta["inference_outcome"] = {
            "outcome": "analysed",
            "measurements": [{"name": "inundation_area", "value": area_ha, "unit": "ha"}],
            "confidence": {"value": result["confidence_score"]},
            "degraded_from": "pinned_demo_baseline",
        }
        new_meta["demo_affected_structures_count"] = result.get("affected_structures_count")
        return {"status": "ANALYZING", "metadata": new_meta}

    assets = obs.get("assets", {})
    vv_href = assets.get("vv") or assets.get("VV")
    vh_href = assets.get("vh") or assets.get("VH")
    if not vv_href or not vh_href:
        new_meta["inference_outcome"] = {
            "outcome": "abstained",
            "reason": "MISSING_REQUIRED_ASSET",
            "explanation": "Live flood inference requires both Sentinel-1 VV and VH assets.",
        }
        return {"status": "FAILED", "metadata": new_meta}

    scene_info = obs.get("scene", {})
    acquired_at = scene_info.get("acquired_at")
    if hasattr(acquired_at, "isoformat"):
        acquired_at = acquired_at.isoformat()
    if not acquired_at:
        new_meta["inference_outcome"] = {
            "outcome": "abstained",
            "reason": "MISSING_ACQUISITION_TIME",
            "explanation": "The selected scene has no acquisition time in its catalogue record.",
        }
        return {"status": "FAILED", "metadata": new_meta}

    # The user's AOI, not the scene footprint: a Sentinel-1 footprint is ~250 km
    # across, and windowing to it reads (and measures) far more than was asked.
    geometry = aoi_geometry(state.aoi)
    payload = {
        "scene": _build_inference_scene(scene_info, scene_id, vv_href, acquired_at),
        "scene_href": vv_href,
        "scene_assets": {"vv": vv_href, "vh": vh_href},
        "aoi_bbox": aoi_bbox(state.aoi),
        "aoi_geometry": geometry,
        "min_mapping_unit_ha": 0.5,
    }

    async def _call_inference():
        client = InternalClient(
            base_url=settings.inference_service_url,
            caller_service="agent",
            scopes=["inference:run"],
            timeout=_inference_timeout_s(),
            # A timed-out analysis may still be running; retrying would start a
            # second copy of the same expensive read.
            max_attempts=1,
        )
        try:
            resp = await client.post("/api/v1/inference/analyses", auth_context=ctx, json=payload)
            return resp.json()
        finally:
            await client.aclose()

    new_meta["analysed_observation_ids"] = list(
        dict.fromkeys(list(state.metadata.get("analysed_observation_ids", [])) + [scene_id])
    )
    try:
        # A fresh event loop in a worker thread: the graph may itself be running
        # inside a loop (eager Celery, tests), where asyncio.run would fail.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            outcome_data = pool.submit(asyncio.run, _call_inference()).result()
    except Exception as e:
        logger.error("Inference call failed: %s", e)
        new_meta["inference_outcome"] = {
            "outcome": "abstained",
            "reason": "INFERENCE_UNAVAILABLE",
            "explanation": f"The inference service could not be reached or failed: {e}",
        }
        return {"status": "FAILED", "metadata": new_meta}

    new_meta["inference_outcome"] = outcome_data
    emit_agent_thought(
        state.mission_id,
        state.trace_id,
        "analyzing",
        "Water segmentation complete; the confidence gate runs next.",
    )
    return {"status": "ANALYZING", "metadata": new_meta}


def _temporal_lag_days(state: MissionState, acquired_at: Optional[str]) -> Optional[float]:
    """Days between the scene and the period the question is about.

    With a caller window: 0 inside it, else the distance to its nearest edge.
    Without one: the scene's age (now - acquisition). None when the scene has
    no parseable acquisition time.
    """
    acquired = _parse_instant(acquired_at)
    if acquired is None:
        return None
    try:
        window = requested_window(state.temporal_window)
    except ValueError:
        window = None
    if window:
        start, end = window
        if start <= acquired <= end:
            return 0.0
        gap = (start - acquired) if acquired < start else (acquired - end)
        return gap.total_seconds() / 86400.0
    return max(0.0, (datetime.now(timezone.utc) - acquired).total_seconds() / 86400.0)


def gate_check(state: MissionState) -> dict:
    ev_builder = EvidenceGraphBuilder(mission_id=state.mission_id)
    new_meta = dict(state.metadata)

    outcome_data = state.metadata.get("inference_outcome") or {}
    acquisition_error = state.metadata.get("acquisition_error")
    if acquisition_error or not outcome_data:
        new_meta["inference_abstention"] = acquisition_error or {
            "reason": "NO_INFERENCE",
            "explanation": "No analysis was run.",
        }
        return {
            "status": "FAILED",
            "confidence_score": 0.0,
            "evidence_graph": {},
            "metadata": new_meta,
        }

    if outcome_data.get("outcome") == "abstained":
        # An abstention is a valid inference response, but it is not a measured
        # zero. Never turn it into a result by defaulting the measurements to 0.
        new_meta["inference_abstention"] = {
            "reason": outcome_data.get("reason"),
            "explanation": outcome_data.get("explanation"),
        }
        return {
            "status": "FAILED",
            "confidence_score": 0.0,
            "evidence_graph": {},
            "metadata": new_meta,
        }

    if not state.observation_ids:
        return {
            "status": "FAILED",
            "confidence_score": 0.0,
            "evidence_graph": {},
            "metadata": new_meta,
        }

    # The measurement: Decimal-as-string from the API, in hectares.
    measurements = outcome_data.get("measurements") or []
    area = next(
        (
            m
            for m in measurements
            if str(m.get("unit", "ha")).lower() in ("ha", "hectare", "hectares")
        ),
        measurements[0] if measurements else None,
    )
    area_value = _as_float(area.get("value")) if area else None
    if area_value is None:
        new_meta["inference_abstention"] = {
            "reason": "NO_MEASUREMENT",
            "explanation": "The analysis returned no readable area measurement.",
        }
        return {
            "status": "FAILED",
            "confidence_score": 0.0,
            "evidence_graph": {},
            "metadata": new_meta,
        }
    unit = str(area.get("unit", "ha")).lower()
    inundated_sqkm = area_value / 100.0 if unit.startswith("ha") else area_value

    obs = _selected_observation(state)
    obs_id = obs.get("observation_id") or state.observation_ids[0]
    scene = obs.get("scene", {})
    obs_time = scene.get("acquired_at")
    sensor = sensor_of(obs) if obs else "S1_SAR"

    obs_node = ev_builder.add_observation(
        {
            "asset_id": obs_id,
            "sensor": sensor,
            "datetime": obs_time,
            "collection": scene.get("collection"),
            "platform": scene.get("platform"),
        }
    )

    # Model confidence exactly as the inference service reported it. The
    # baseline is NOT_CALIBRATED and reports None; that is carried through as
    # None rather than replaced with a plausible-looking number.
    conf_data = outcome_data.get("confidence") or {}
    model_conf = _as_float(conf_data.get("value"))
    confidence_basis = conf_data.get("basis") or (
        "REPORTED" if model_conf is not None else "NOT_CALIBRATED"
    )

    produced_by = next(
        (
            c.split("produced by ", 1)[1]
            for c in outcome_data.get("caveats", [])
            if isinstance(c, str) and c.startswith("produced by ")
        ),
        None,
    )
    # "produced by <method>" names the method (model card or baseline); the
    # measurement's own produced_by names the area function, so it is last.
    model_name = (
        produced_by or outcome_data.get("degraded_from") or area.get("produced_by") or "unknown"
    )
    inf_node = ev_builder.add_inference(
        input_node_ids=[obs_node.node_id],
        model_name=str(model_name),
        model_version=str(area.get("code_version") or "unversioned"),
        results={
            "inundated_sqkm": inundated_sqkm,
            "degraded_from": outcome_data.get("degraded_from"),
            "confidence_basis": confidence_basis,
            "inference_trace_id": outcome_data.get("trace_id"),
        },
        confidence=model_conf,
    )
    ev_builder.add_metric(
        inference_node_id=inf_node.node_id,
        metric_name="inundation_area_sqkm",
        value=inundated_sqkm,
        unit="km2",
    )
    if state.metadata.get("demo_affected_structures_count") is not None:
        ev_builder.add_metric(
            inference_node_id=inf_node.node_id,
            metric_name="affected_structures_count",
            value=float(state.metadata["demo_affected_structures_count"]),
            unit="count",
        )

    evidence_graph = ev_builder.build().model_dump()

    # Gate inputs from the scene itself.
    props = obs.get("normalized_properties") or {}
    resolution = _as_float(props.get("resolution_m") or props.get("gsd")) or (
        _S1_RTC_RESOLUTION_M if sensor == "S1_SAR" else 10.0
    )
    cloud = 0.0 if sensor == "S1_SAR" else (_as_float(scene.get("cloud_cover")) or 0.0)
    lag = _temporal_lag_days(state, obs_time)

    conf = evaluate_confidence_gate(
        evidence_nodes=list(evidence_graph.get("nodes", {}).values()),
        sensor_type=sensor,
        cloud_cover=min(100.0, max(0.0, cloud)),
        resolution_meters=resolution,
        temporal_lag_days=lag if lag is not None else 0.0,
        trace_id=state.trace_id,
    )
    uncertainty = list(conf.uncertainty_factors)
    if lag is None:
        uncertainty.append("Scene acquisition time unknown; temporal lag not assessed")
    for caveat in outcome_data.get("caveats", []) or []:
        if isinstance(caveat, str) and caveat.startswith("degraded:"):
            uncertainty.append(f"Inference {caveat}")

    new_meta["confidence"] = {
        "score": conf.confidence_score,
        "passed_gate": conf.passed_gate,
        "model_confidence": model_conf,
        "model_confidence_basis": confidence_basis,
        "score_basis": (
            "acquisition_quality_and_model"
            if model_conf is not None
            else "acquisition_quality_only"
        ),
        "inputs": {
            "sensor": sensor,
            "resolution_m": resolution,
            "cloud_cover": cloud if sensor != "S1_SAR" else None,
            "temporal_lag_days": round(lag, 1) if lag is not None else None,
        },
    }
    new_meta["inference_summary"] = {
        "trace_id": outcome_data.get("trace_id"),
        "geometry_ref": outcome_data.get("geometry_ref"),
        "degraded_from": outcome_data.get("degraded_from"),
        "produced_by": produced_by,
        "caveats": list(outcome_data.get("caveats", []) or []),
    }

    status = "GATE_CHECK"
    if not conf.passed_gate:
        retries = new_meta.get("reinvestigations", 0)
        box = None
        try:
            box = aoi_bbox(state.aoi)
        except AOIError:
            pass
        alternatives = (
            rank_sar_scenes(
                state.metadata.get("observations", []),
                box,
                exclude=state.metadata.get("analysed_observation_ids", []),
            )
            if box
            else []
        )
        if retries < 1 and alternatives:
            new_meta["reinvestigations"] = retries + 1
            status = "REINVESTIGATE"
        elif not alternatives:
            uncertainty.append("No other analysable scene was available to cross-check")

    return {
        "status": status,
        "confidence_score": conf.confidence_score,
        "uncertainty_reasons": uncertainty,
        "evidence_graph": evidence_graph,
        "metadata": new_meta,
    }


#: Below this the run is reported as failed rather than as a finding.
REPORTING_THRESHOLD = 0.6


def synthesize(state: MissionState) -> dict:
    abstention = state.metadata.get("inference_abstention")
    if abstention:
        reason = abstention.get("explanation") or abstention.get("reason")
        code = abstention.get("reason")
        acquisition = bool(state.metadata.get("acquisition_error"))
        lead = (
            "The run stopped before analysis."
            if acquisition
            else "No reliable measurement was produced; the inference service abstained."
        )
        output_dict = {
            "summary": f"{lead} Reason: {reason}." if reason else lead,
            "failure_reason": code,
            "inundation_area_sqkm": None,
            "affected_structures_count": None,
            "primary_sensor": None,
            "search": state.metadata.get("search"),
        }
        return {"status": "FAILED", "synthesized_output": output_dict}

    if not (state.evidence_graph and state.observation_ids):
        reason = "No observations acquired." if not state.observation_ids else "No evidence graph available for synthesis."
        return {
            "status": "FAILED",
            "synthesized_output": {
                "summary": f"Mission failed to complete. Reason: {reason}",
                "failure_reason": "NO_EVIDENCE",
                "inundation_area_sqkm": None,
                "affected_structures_count": None,
                "primary_sensor": None,
            },
        }

    if state.confidence_score is not None and state.confidence_score < REPORTING_THRESHOLD:
        return {
            "status": "FAILED",
            "synthesized_output": {
                "summary": (
                    f"An extent was measured, but the confidence gate scored it "
                    f"{state.confidence_score:.2f}, below the {REPORTING_THRESHOLD:.2f} reporting "
                    "threshold, so it is not reported as a finding."
                ),
                "failure_reason": "LOW_CONFIDENCE",
                "inundation_area_sqkm": None,
                "affected_structures_count": None,
                "primary_sensor": None,
                "uncertainty_reasons": list(state.uncertainty_reasons),
            },
        }

    try:
        graph = EvidenceGraph(**state.evidence_graph)
        out = synthesize_evidence_output(
            graph,
            state.sanitized_query or state.query,
            context={
                "sensor_decision": state.metadata.get("sensor_decision"),
                "confidence": state.metadata.get("confidence"),
                "inference": state.metadata.get("inference_summary"),
                "uncertainty_reasons": list(state.uncertainty_reasons),
                "search": state.metadata.get("search"),
                "scene_coverage": state.metadata.get("selected_scene_coverage"),
            },
        )
    except ValueError as e:
        return {
            "status": "FAILED",
            "synthesized_output": {
                "summary": f"Evidence synthesis failed: {e}",
                "failure_reason": "SYNTHESIS_FAILED",
                "inundation_area_sqkm": None,
                "affected_structures_count": None,
                "primary_sensor": None,
            },
        }

    output_dict = out.model_dump()
    # Flatten metrics into top-level for backward compatibility
    for k, v in out.metrics.items():
        output_dict[k] = v
    obs = _selected_observation(state)
    output_dict["primary_sensor"] = sensor_of(obs) if obs else None
    output_dict["observation_id"] = obs.get("observation_id")
    output_dict["acquired_at"] = (obs.get("scene") or {}).get("acquired_at")
    output_dict["inference"] = state.metadata.get("inference_summary")
    output_dict["confidence"] = state.metadata.get("confidence")
    output_dict["search"] = state.metadata.get("search")
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

    Run state lives in Redis (``agent:run:{job_id}``, 24h TTL) with a
    process-local cache in front. The cache keeps same-process reads cheap;
    Redis is what makes a run visible across processes — the API process that
    creates it, the process that streams the graph (a daemon thread here, or a
    Celery worker — either executor works once state is shared), the mission
    service polling GET /agent/runs/{job_id}, and the gateway WS bridging
    progress to the browser. Redis writes are best-effort: if Redis is down the
    run still executes, but only this process can see it.
    """

    RUN_KEY_PREFIX = "agent:run:"
    RUN_TTL_SECONDS = 24 * 3600

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
        temporal_window: Optional[Dict] = None,
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
            temporal_window=temporal_window,
            status="INITIALIZED",
            metadata=metadata or {},
        )
        self.save_run(state)
        return state

    def save_run(self, state: MissionState) -> None:
        """Persist run state: process-local cache first, then Redis (best-effort)."""
        if state.job_id:
            self._runs[state.job_id] = state
        try:
            self._get_redis().set(
                self.RUN_KEY_PREFIX + (state.job_id or state.run_id),
                state.model_dump_json(),
                ex=self.RUN_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001 — a state store outage must not kill a run
            logger.warning(
                "Run state not persisted to Redis (job_id=%s): %s", state.job_id, exc
            )

    TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED"})

    def get_run(self, job_id: str) -> Optional[MissionState]:
        """Latest known state of a run.

        A terminal run cannot change, so the local cache answers. A run still in
        progress may be advancing in another process (a Celery worker), so Redis
        is read first and the cache is only the fallback when Redis is down.
        """
        cached = self._runs.get(job_id)
        if cached is not None and cached.status in self.TERMINAL_STATUSES:
            return cached
        try:
            raw = self._get_redis().get(self.RUN_KEY_PREFIX + job_id)
        except Exception:  # noqa: BLE001 — an unreadable store falls back to the cache
            return cached
        if not raw:
            return cached
        try:
            state = MissionState.model_validate_json(raw)
        except Exception:  # noqa: BLE001 — a corrupt entry must not 500 the route
            logger.exception("Stored run %s is not a valid MissionState.", job_id)
            return cached
        self._runs[job_id] = state
        return state

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
            current_state_dict["updated_at"] = datetime.now(timezone.utc)

            temp_state = MissionState(**current_state_dict)
            # Persist after every node so a poller sees progress, not just the end.
            if temp_state.job_id:
                self.save_run(temp_state)
            self._publish_event(temp_state, f"NODE_COMPLETED_{node_name.upper()}", {"status": temp_state.status})

        final_state = MissionState(**current_state_dict)
        if final_state.job_id:
            self.save_run(final_state)

        self._publish_event(final_state, "RUN_COMPLETED", {"status": final_state.status})
        return final_state


_default_orchestrator = AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    return _default_orchestrator
