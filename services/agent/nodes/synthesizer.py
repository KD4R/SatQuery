"""
nodes/synthesizer.py — Grounded evidence output synthesizer and WHY explanation generator.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from services.agent.evidence.models import EvidenceGraph, EvidenceNodeType
from services.agent.config import get_agent_settings

logger = logging.getLogger(__name__)


class SynthesizedOutput(BaseModel):
    """Factual, evidence-grounded summary with citations and explicit WHY explanations."""

    summary: str
    citations: List[str] = Field(
        default_factory=list, description="IDs of evidence nodes supporting this synthesis"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Verified numerical findings from evidence graph"
    )
    why_explanation: Dict[str, str] = Field(
        default_factory=dict, description="Transparent rationale behind decisions"
    )
    grounding_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="1.0 indicates 100% evidence-backed statements"
    )


def _fmt_area(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{v:,.2f}" if v < 100 else f"{v:,.1f}"


def _why_from_context(
    context: Dict[str, Any], models_used: List[str], sensors: List[str] | None = None
) -> Dict[str, str]:
    """Build the WHY explanation from what this run actually did.

    Every sentence is derived from run data (the arbitration decision, the
    inference caveats, the gate inputs). A field with no data behind it is
    omitted rather than filled with generic prose.
    """
    why: Dict[str, str] = {}

    decision = context.get("sensor_decision") or {}
    if decision.get("rationale"):
        why["sensor_choice"] = str(decision["rationale"])
    elif sensors:
        names = {
            "S1_SAR": "Sentinel-1 SAR (C-band, images through cloud and at night)",
            "S2_OPTICAL": "Sentinel-2 optical (multispectral, needs clear sky)",
        }
        why["sensor_choice"] = (
            "Evidence came from " + "; ".join(names.get(s, s) for s in dict.fromkeys(sensors)) + "."
        )

    conf = context.get("confidence") or {}
    reasons = [r for r in (context.get("uncertainty_reasons") or []) if r]
    if conf:
        inputs = conf.get("inputs") or {}
        parts = [f"Gate score {conf.get('score')}"]
        if conf.get("model_confidence") is None:
            parts.append(
                "model confidence not calibrated, so the score reflects acquisition quality only"
            )
        else:
            basis = conf.get("model_confidence_basis")
            parts.append(f"model confidence {conf.get('model_confidence')} ({basis})")
        if inputs.get("resolution_m") is not None:
            parts.append(f"{inputs['resolution_m']:g} m pixels")
        lag = inputs.get("temporal_lag_days")
        if lag is not None:
            parts.append(
                "scene is inside the requested window"
                if lag == 0
                else f"scene is {lag} days from the requested period"
            )
        text = "; ".join(parts) + "."
        extra = [r for r in reasons if "not calibrated" not in r.lower()]
        if extra:
            text += " Caveats: " + "; ".join(extra) + "."
        why["confidence_rationale"] = text

    inference = context.get("inference") or {}
    caveats = [c for c in (inference.get("caveats") or []) if isinstance(c, str)]
    method_bits = []
    if inference.get("produced_by") or models_used:
        method_bits.append(f"Method: {inference.get('produced_by') or ', '.join(models_used)}")
    if inference.get("degraded_from") and inference.get("degraded_from") != inference.get(
        "produced_by"
    ):
        method_bits.append(f"fallback from {inference['degraded_from']}")
    method_caveats = [
        c for c in caveats if not c.startswith("produced by ") and not c.startswith("degraded:")
    ]
    if method_bits or method_caveats:
        why["methodology"] = (
            ". ".join([", ".join(method_bits)] + method_caveats if method_bits else method_caveats)
            + "."
        )

    coverage = context.get("scene_coverage")
    if coverage is not None and coverage < 0.98:
        why["coverage"] = (
            f"The selected scene covers about {coverage:.0%} of the AOI's bounding box; "
            "the area outside it was not observed."
        )
    return why


def synthesize_evidence_output(
    graph: EvidenceGraph,
    user_query: str,
    context: Dict[str, Any] | None = None,
) -> SynthesizedOutput:
    """
    Synthesizes facts strictly grounded in the EvidenceGraph.
    Never invents observations or numerical measurements.
    """
    if not graph.nodes:
        raise ValueError("Cannot synthesize output from an empty EvidenceGraph")
    context = context or {}

    citations: List[str] = []
    metrics: Dict[str, Any] = {}
    observations: List[str] = []
    models_used: List[str] = []
    sensors: List[str] = []

    for nid, node in graph.nodes.items():
        citations.append(nid)
        if node.node_type == EvidenceNodeType.OBSERVATION:
            sensor = node.data.get("sensor", "UNKNOWN")
            sensors.append(sensor)
            when = node.data.get("datetime")
            label = f"{sensor} ({node.data.get('asset_id', nid)})"
            observations.append(f"{label} acquired {when}" if when else label)
        elif node.node_type == EvidenceNodeType.METRIC:
            metric_name = node.data.get("metric_name", "value")
            metrics[metric_name] = node.data.get("value")
        elif node.node_type == EvidenceNodeType.INFERENCE:
            models_used.append(node.source)

    area = metrics.get("inundation_area_sqkm")
    source = (
        f"{len(observations)} observation(s) ({'; '.join(observations)}) "
        f"using {', '.join(models_used) or 'no recorded model'}"
    )
    if area is not None:
        deterministic_summary = (
            f"{_fmt_area(area)} km² of surface water was mapped inside the AOI from "
            f"{source}. This is open water on the acquisition date; it includes "
            "permanent water bodies unless a permanent-water layer was applied."
        )
    elif metrics:
        listed = ", ".join(f"{k} = {v}" for k, v in metrics.items())
        deterministic_summary = f"Measured from {source}: {listed}."
    else:
        deterministic_summary = f"Evidence from {source}; no metric was measured."

    llm_summary = _grounded_llm_summary(
        user_query=user_query,
        deterministic_summary=deterministic_summary,
        observations=observations,
        models_used=models_used,
        metrics=metrics,
        citations=citations,
    )
    summary = (
        llm_summary
        if llm_summary
        and _numbers_are_grounded(
            llm_summary,
            [deterministic_summary, json.dumps(metrics, default=str), " ".join(citations)],
        )
        else deterministic_summary
    )

    return SynthesizedOutput(
        summary=summary,
        citations=citations,
        metrics=metrics,
        why_explanation=_why_from_context(context, models_used, sensors),
        # 1.0 is now true by construction: an LLM summary containing any number
        # not present in the verified facts is discarded for the deterministic one.
        grounding_score=1.0,
    )


_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def _numbers_are_grounded(text: str, sources: List[str]) -> bool:
    """True when every number in ``text`` also appears in one of ``sources``.

    Guards the LLM prose: it may rephrase, it may not introduce a figure.
    Evidence ids (e.g. ``inf_1a2b3c``) are excluded by the word-boundary rule.
    """
    haystack = " ".join(sources)
    known = {n.replace(",", "") for n in _NUMBER.findall(haystack)}
    # Allow the same value at other precisions (e.g. 12.35 vs 12.3456).
    known_floats = set()
    for n in known:
        try:
            known_floats.add(float(n))
        except ValueError:
            pass
    for raw in _NUMBER.findall(text):
        n = raw.replace(",", "")
        if n in known:
            continue
        try:
            v = float(n)
        except ValueError:
            return False
        decimals = len(n.split(".")[1]) if "." in n else 0
        if not any(round(k, decimals) == v for k in known_floats):
            return False
    return True


def _grounded_llm_summary(
    *,
    user_query: str,
    deterministic_summary: str,
    observations: List[str],
    models_used: List[str],
    metrics: Dict[str, Any],
    citations: List[str],
) -> str | None:
    """Ask Groq for presentation prose using only already-verified facts.

    Numerical values remain owned by the evidence graph. If the provider is
    unavailable, the deterministic summary is returned by the caller.
    """
    settings = get_agent_settings()
    api_key = settings.groq_api_key or settings.openai_api_key
    if not api_key:
        return None

    model = settings.llm_model if settings.groq_api_key else "gpt-4o"
    kwargs: Dict[str, Any] = {
        "model": model,
        "openai_api_key": SecretStr(api_key),
        "temperature": 0.0,
        "max_tokens": 180,
        # A slow provider must not hold the run: fall back to the deterministic
        # summary after this long.
        "timeout": float(os.getenv("AGENT_LLM_TIMEOUT_S", "20")),
        "max_retries": 1,
    }
    if settings.groq_api_key:
        kwargs["base_url"] = "https://api.groq.com/openai/v1"

    facts = {
        "user_question": user_query,
        "verified_summary": deterministic_summary,
        "observations": observations,
        "models": models_used,
        "verified_metrics": metrics,
        "evidence_ids": citations,
    }
    prompt = (
        "Write one concise, professional satellite-analysis answer using only the "
        "verified facts below. Do not invent facts, dates, locations, confidence, "
        "measurements, or recommendations. Preserve every numeric value exactly. "
        "Mention the sensor/model and cite evidence IDs in parentheses. If the "
        "verified summary says no reliable measurement was produced, say that "
        "plainly instead of implying a zero result. Return prose only.\n\n"
        + json.dumps(facts, default=str)
    )
    try:
        response = ChatOpenAI(**kwargs).invoke(prompt)
        content = response.content
        if isinstance(content, str) and content.strip():
            return content.strip()
    except Exception:
        logger.exception("Grounded LLM synthesis failed; using deterministic summary")
    return None
