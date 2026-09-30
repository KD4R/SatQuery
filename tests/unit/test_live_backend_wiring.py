"""
tests/unit/test_live_backend_wiring.py

End-to-end agent run with the two external systems stubbed at their edges (the
STAC search tool and the inference HTTP call), checking the fixes that connect
the dashboard's live path to real numbers:

  * the user's AOI and time window drive the search (no default Assam bbox);
  * the newest Sentinel-1 scene that covers the AOI is analysed;
  * inference receives the AOI window/polygon, not the 250 km scene footprint;
  * Decimal-as-string measurements are read (they used to crash the gate);
  * a NOT_CALIBRATED confidence stays None (it used to become 0.88);
  * the run is persisted after every node and signed URLs never leave the service.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.agent.graph import orchestrator as orch
from services.agent.graph.run_inputs import (
    AOIError,
    aoi_bbox,
    aoi_geometry,
    rank_sar_scenes,
    redact_signed_urls,
    requested_window,
)

AOI = {
    "type": "Polygon",
    "coordinates": [
        [[92.60, 26.30], [92.80, 26.30], [92.80, 26.45], [92.60, 26.45], [92.60, 26.30]]
    ],
}
EVENT = datetime(2024, 7, 5, 0, 0, tzinfo=timezone.utc)
SAS = "?st=2024-07-01&se=2024-07-02&sp=rl&sig=SECRET"


def _obs(obs_id, acquired, footprint, collection="sentinel-1-rtc", dual=True):
    assets = {"vv": f"https://sentinel1euwestrtc.blob.core.windows.net/x/{obs_id}/vv.tif{SAS}"}
    if dual:
        assets["vh"] = f"https://sentinel1euwestrtc.blob.core.windows.net/x/{obs_id}/vh.tif{SAS}"
    w, s, e, n = footprint
    return {
        "observation_id": obs_id,
        "scene": {
            "provider": "planetary_computer",
            "collection": collection,
            "item_id": obs_id,
            "acquired_at": acquired.isoformat(),
            "platform": "SENTINEL-1A" if "sentinel-1" in collection else "Sentinel-2A",
            "instrument": "C-SAR" if "sentinel-1" in collection else "MSI",
            "relative_orbit": 12,
            "pass_direction": "ASCENDING",
            "href": f"https://planetarycomputer.microsoft.com/api/stac/v1/items/{obs_id}",
            "cloud_cover": None,
        },
        "geometry": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]},
        "assets": assets,
        "normalized_properties": {},
    }


FULL = (91.5, 25.5, 94.0, 27.5)
PARTIAL = (92.70, 25.5, 94.0, 27.5)  # misses the western half of the AOI

OBSERVATIONS = [
    _obs("S1_OLD_FULL", EVENT - timedelta(days=4), FULL),
    _obs("S1_NEWEST_PARTIAL", EVENT + timedelta(days=1), PARTIAL),
    _obs("S1_NEW_FULL", EVENT - timedelta(days=1), FULL),
    _obs("S1_NEW_FULL_SINGLEPOL", EVENT, FULL, dual=False),
    _obs("S2_OPTICAL", EVENT, FULL, collection="sentinel-2-l2a"),
]

INFERENCE_TRACE = "7d3c1f7e-2c49-4a3e-9d7b-0a1f5e6c9b11"
ANALYSIS = {
    "outcome": "analysed",
    "measurements": [
        {
            "name": "water_extent",
            "value": "1234.5",  # Decimal serialises as a JSON string
            "unit": "ha",
            "produced_by": "ml.geo.area.area_hectares",
            "code_version": "c50604b",
            "crs": "EPSG:32646",
            "derived_from": [],
        }
    ],
    "geometry_ref": f"analyses/{INFERENCE_TRACE}/water_extent.geojson",
    "raster_refs": [f"analyses/{INFERENCE_TRACE}/water_mask.tif"],
    "confidence": {
        "basis": "not_calibrated",
        "value": None,
        "interval": None,
        "calibration_ref": None,
        "agreement_iou": None,
        "caveats": ["deterministic baseline; no calibration report exists for it"],
    },
    "scenes": [],
    "degraded_from": "deterministic-otsu-baseline",
    "caveats": [
        "produced by deterministic-otsu-baseline",
        "single-date Otsu on VV; threshold -17.20 dB",
        "degraded: no registered model beats the deterministic baseline on held-out "
        "regions, so the baseline was used",
    ],
    "trace_id": INFERENCE_TRACE,
}


@pytest.fixture
def stubbed(monkeypatch):
    no_llm = SimpleNamespace(
        groq_api_key=None,
        openai_api_key=None,
        llm_model="none",
        inference_service_url="http://inference:8000",
    )
    monkeypatch.setattr("services.agent.nodes.intent_extractor.get_agent_settings", lambda: no_llm)
    monkeypatch.setattr("services.agent.nodes.synthesizer.get_agent_settings", lambda: no_llm)
    monkeypatch.setattr("services.agent.config.get_agent_settings", lambda: no_llm)

    calls = {"search": [], "inference": []}

    def execute_tool(name, args, auth_context, budget=None):
        calls["search"].append(args)
        return SimpleNamespace(
            success=True, output=[dict(o) for o in OBSERVATIONS], error=None, metadata={}
        )

    executor = MagicMock()
    executor.execute_tool.side_effect = execute_tool
    monkeypatch.setattr(orch, "get_tool_executor", lambda: executor)

    async def post(self, path, auth_context, **kwargs):
        calls["inference"].append(
            {
                "path": path,
                "json": kwargs["json"],
                "timeout": self.timeout,
                "max_attempts": self.max_attempts,
            }
        )
        resp = MagicMock()
        resp.json.return_value = ANALYSIS
        return resp

    monkeypatch.setattr("packages.shared.client.InternalClient.post", post)
    return calls


def _run(temporal_window=None, aoi=AOI):
    o = orch.AgentOrchestrator()
    saved = []
    real_save = o.save_run
    o.save_run = lambda st: (saved.append(st.status), real_save(st))
    state = o.create_run(
        mission_id="msn-live-1",
        org_id="org-test",
        query="Map flooding around Nagaon",
        aoi=aoi,
        temporal_window=temporal_window,
    )
    return o.step_execution(state), saved


@pytest.mark.unit
def test_live_run_completes_with_real_numbers(stubbed):
    window = {
        "start": (EVENT - timedelta(days=6)).isoformat(),
        "end": (EVENT + timedelta(days=1)).isoformat(),
    }
    final, saved = _run(temporal_window=window)

    assert final.status == "COMPLETED", final.synthesized_output
    out = final.synthesized_output
    # 1234.5 ha -> 12.345 km², read from a string
    assert out["inundation_area_sqkm"] == pytest.approx(12.345)
    assert out["primary_sensor"] == "S1_SAR"
    # The newest scene that covers the whole AOI, not observation_ids[0]
    assert out["observation_id"] == "S1_NEW_FULL"
    assert out["inference"]["trace_id"] == INFERENCE_TRACE
    assert out["inference"]["geometry_ref"].endswith("water_extent.geojson")

    # NOT_CALIBRATED stays None; the score is acquisition quality only
    conf = final.metadata["confidence"]
    assert conf["model_confidence"] is None
    assert conf["score_basis"] == "acquisition_quality_only"
    inf_nodes = [n for n in final.evidence_graph["nodes"].values() if n["node_type"] == "INFERENCE"]
    assert inf_nodes[0]["confidence"] is None
    assert any("not calibrated" in r for r in final.uncertainty_reasons)
    assert any("degraded" in r for r in final.uncertainty_reasons)

    # WHY comes from this run, not boilerplate
    why = out["why_explanation"]
    assert "Sentinel-1" in why["sensor_choice"]
    assert "deterministic-otsu-baseline" in why["methodology"]
    assert "acquisition quality" in why["confidence_rationale"]

    # The caller's window was used as-is (one search, no widening)
    assert len(stubbed["search"]) == 1
    assert stubbed["search"][0]["start_date"].startswith("2024-06-29")
    assert stubbed["search"][0]["sensors"] == ["S1_SAR"]
    assert stubbed["search"][0]["bbox"] == pytest.approx([92.60, 26.30, 92.80, 26.45])
    assert final.metadata["search"]["widened"] is False

    # Inference got the AOI, not the scene footprint, and a long, no-retry timeout
    call = stubbed["inference"][0]
    assert call["json"]["aoi_bbox"] == pytest.approx([92.60, 26.30, 92.80, 26.45])
    assert call["json"]["aoi_geometry"]["type"] == "Polygon"
    assert call["json"]["scene"]["item_id"] == "S1_NEW_FULL"
    assert call["timeout"] >= 120 and call["max_attempts"] == 1

    # Persisted after every node, not only at the end
    assert saved[0] == "INITIALIZED"
    assert {"PLANNING", "ARBITRATING", "ACQUIRING", "ANALYZING", "GATE_CHECK"} <= set(saved)
    assert saved[-1] == "COMPLETED"


@pytest.mark.unit
def test_public_view_strips_sas_tokens(stubbed):
    final, _ = _run(temporal_window={"event_date": EVENT.isoformat()})
    internal = final.model_dump_json()
    assert "sig=SECRET" in internal  # inference needs the signed URL
    public = str(redact_signed_urls(final.model_dump()))
    assert "sig=SECRET" not in public
    assert "sentinel1euwestrtc.blob.core.windows.net/x/S1_NEW_FULL/vv.tif" in public


@pytest.mark.unit
def test_run_without_aoi_fails_fast_and_searches_nothing(stubbed):
    final, _ = _run(aoi=None)
    assert final.status == "FAILED"
    assert final.synthesized_output["failure_reason"] == "AOI_REQUIRED"
    assert stubbed["search"] == [] and stubbed["inference"] == []


@pytest.mark.unit
def test_no_window_searches_90_days_then_widens(stubbed, monkeypatch):
    def empty_then_full(name, args, auth_context, budget=None):
        stubbed["search"].append(args)
        out = [] if len(stubbed["search"]) == 1 else [dict(o) for o in OBSERVATIONS]
        return SimpleNamespace(success=True, output=out, error=None, metadata={})

    executor = MagicMock()
    executor.execute_tool.side_effect = empty_then_full
    monkeypatch.setattr(orch, "get_tool_executor", lambda: executor)
    final, _ = _run()
    assert len(stubbed["search"]) == 2
    assert final.metadata["search"]["widened"] is True
    # Old scene vs now: the gate penalises the lag instead of hiding it
    assert final.metadata["confidence"]["inputs"]["temporal_lag_days"] > 14


@pytest.mark.unit
def test_abstention_is_reported_not_zeroed(stubbed, monkeypatch):
    async def post(self, path, auth_context, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {
            "outcome": "abstained",
            "reason": "no_separable_threshold",
            "explanation": "histogram is unimodal",
            "nearest_usable": None,
            "scenes_seen": [],
            "trace_id": INFERENCE_TRACE,
        }
        return resp

    monkeypatch.setattr("packages.shared.client.InternalClient.post", post)
    final, _ = _run(temporal_window={"event_date": EVENT.isoformat()})
    assert final.status == "FAILED"
    assert final.synthesized_output["inundation_area_sqkm"] is None
    assert "unimodal" in final.synthesized_output["summary"]


# ── helpers ──────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_aoi_shapes():
    feature = {"type": "Feature", "geometry": AOI, "properties": {}}
    fc = {"type": "FeatureCollection", "features": [feature, feature]}
    assert aoi_bbox(feature) == pytest.approx([92.60, 26.30, 92.80, 26.45])
    assert aoi_geometry(fc)["type"] == "MultiPolygon"
    assert aoi_bbox({"bbox": [1, 2, 3, 4]}) == [1, 2, 3, 4]
    with pytest.raises(AOIError):
        aoi_bbox(None)
    with pytest.raises(AOIError):
        aoi_geometry({"type": "Point", "coordinates": [1, 2]})


@pytest.mark.unit
def test_requested_window_forms():
    s, e = requested_window({"event_date": "2024-07-05"})
    assert (e - s).days == 12
    assert requested_window(None) is None
    with pytest.raises(ValueError):
        requested_window({"start": "2024-07-05", "end": "2024-07-01"})
    with pytest.raises(ValueError):
        requested_window({"nonsense": 1})


@pytest.mark.unit
def test_scene_ranking_prefers_full_coverage_then_recency():
    ranked = rank_sar_scenes(OBSERVATIONS, [92.60, 26.30, 92.80, 26.45])
    ids = [o["observation_id"] for o in ranked]
    assert ids[0] == "S1_NEW_FULL"
    assert "S2_OPTICAL" not in ids and "S1_NEW_FULL_SINGLEPOL" not in ids
    assert ids[-1] == "S1_NEWEST_PARTIAL"
    again = rank_sar_scenes(OBSERVATIONS, [92.60, 26.30, 92.80, 26.45], exclude=["S1_NEW_FULL"])
    assert again[0]["observation_id"] == "S1_OLD_FULL"


@pytest.mark.unit
def test_get_run_prefers_redis_for_in_progress_runs():
    o = orch.AgentOrchestrator()
    fake = MagicMock()
    o._redis = fake
    state = o.create_run(mission_id="m", org_id="org", query="Map flood extent")
    newer = state.model_copy(update={"status": "ANALYZING"})
    fake.get.return_value = newer.model_dump_json()
    assert o.get_run(state.job_id).status == "ANALYZING"
    # Terminal state in cache answers without Redis
    o._runs[state.job_id] = state.model_copy(update={"status": "COMPLETED"})
    fake.get.side_effect = AssertionError("should not read Redis")
    assert o.get_run(state.job_id).status == "COMPLETED"


@pytest.mark.unit
def test_worker_persists_each_node_and_redacts_publish(stubbed, monkeypatch):
    import json

    from services.agent import worker

    o = orch.AgentOrchestrator()
    saved = []
    o.save_run = lambda st: saved.append(st.status)
    state = o.create_run(
        mission_id="msn-w",
        org_id="org",
        query="Map flood extent",
        aoi=AOI,
        temporal_window={"event_date": EVENT.isoformat()},
    )
    o._runs[state.job_id] = state
    o.get_run = lambda job_id: o._runs.get(job_id)
    monkeypatch.setattr(worker, "get_orchestrator", lambda: o)
    published = []
    monkeypatch.setattr(
        worker, "redis_client", SimpleNamespace(publish=lambda ch, msg: published.append(msg))
    )

    result = worker._stream_run(state.job_id)
    assert result["final_status"] == "COMPLETED"
    assert len(saved) >= 6 and saved[-1] == "COMPLETED"
    assert published and all("sig=SECRET" not in m for m in published)
    assert json.loads(published[-1])["node"] == "synthesize"


@pytest.mark.unit
def test_worker_saves_failed_state_on_crash(monkeypatch):
    from services.agent import worker

    o = orch.AgentOrchestrator()
    saved = []
    state = o.create_run(mission_id="m", org_id="org", query="Map flood extent")
    o.get_run = lambda job_id: state
    o.save_run = lambda st: saved.append(st.status)
    o._app = SimpleNamespace(stream=MagicMock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(worker, "get_orchestrator", lambda: o)
    with pytest.raises(RuntimeError):
        worker._stream_run(state.job_id)
    assert saved == ["FAILED"]
    assert "boom" in state.errors[-1]
