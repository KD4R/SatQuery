/**
 * MissionState → what the console shows for a live run (audit W3, W6, W7, W10).
 *
 * Every field is read from what the agent published (see services/agent/graph/
 * orchestrator.py: synthesize, gate_check, acquire_data). Nothing is defaulted
 * into a plausible value: a missing number stays null and the UI prints "—" or
 * the reason, because a 0 would read as "measured, nothing there".
 */

import type { MissionState } from "../api/types";

/* ── small safe readers ─────────────────────────────────────────────────── */

type Rec = Record<string, unknown>;

function rec(v: unknown): Rec | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Rec) : null;
}
function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}
function num(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "" && Number.isFinite(Number(v))) return Number(v);
  return null;
}
function strList(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && x.length > 0) : [];
}

/* ── view model ─────────────────────────────────────────────────────────── */

export interface SearchAttempt {
  start: string;
  end: string;
  results: number;
  error: string | null;
}

export interface SearchInfo {
  bbox: [number, number, number, number] | null;
  sensors: string[];
  requestedWindow: { start: string; end: string } | null;
  attempts: SearchAttempt[];
  widened: boolean;
}

export interface EvidenceRow {
  id: string;
  type: string;
  title: string;
  detail: string;
  source: string;
  /** null = the producer reported no justified confidence (e.g. NOT_CALIBRATED). */
  confidence: number | null;
}

export interface LiveResult {
  status: "COMPLETED" | "FAILED" | "RUNNING";
  summary: string | null;
  failure: { reason: string | null; text: string | null; hint: string } | null;

  areaKm2: number | null;
  scene: {
    id: string | null;
    acquiredAt: string | null;
    sensor: string | null;
    collection: string | null;
    platform: string | null;
    coverage: number | null;
  };
  confidence: {
    score: number | null;
    passedGate: boolean | null;
    modelConfidence: number | null;
    modelBasis: string | null;
    scoreBasis: string | null;
    resolutionM: number | null;
    lagDays: number | null;
  };
  why: { key: string; title: string; text: string }[];
  uncertainty: string[];
  caveats: string[];
  inference: {
    traceId: string | null;
    geometryRef: string | null;
    degradedFrom: string | null;
    producedBy: string | null;
  };
  search: SearchInfo | null;
  evidence: EvidenceRow[];
  citations: number;
}

const WHY_TITLES: Record<string, string> = {
  sensor_choice: "Why this sensor",
  confidence_rationale: "Why this confidence",
  methodology: "How it was measured",
  coverage: "What the scene covers",
};

/** What to try next, per failure reason the backend reports. */
export function failureHint(reason: string | null): string {
  switch ((reason ?? "").toUpperCase()) {
    case "AOI_REQUIRED":
      return "Draw an area of interest on the map, then run again.";
    case "AOI_TOO_LARGE":
      return "Draw a smaller area (live analysis is limited per run).";
    case "INVALID_TEMPORAL_WINDOW":
      return "Check the dates: the start must be before the end.";
    case "NO_SCENES_IN_WINDOW":
      return "Widen the date range or clear it to let the agent search the last year.";
    case "NO_ANALYSABLE_SCENE":
      return "Scenes exist but none is Sentinel-1 with both VV and VH. Try other dates.";
    case "CATALOGUE_UNAVAILABLE":
      return "The satellite catalogue did not answer. Try again in a minute.";
    case "INFERENCE_UNAVAILABLE":
      return "The inference service could not be reached. Check that it is running.";
    case "LOW_CONFIDENCE":
      return "The evidence was too weak to report. Try a date closer to the event.";
    case "NO_SEPARABLE_THRESHOLD":
      return "Water and land could not be separated in this scene. Try another date or a larger AOI.";
    case "INPUT_FAILED_PREFLIGHT":
      return "The scene could not be read for this AOI. Try a smaller area or other dates.";
    default:
      return "Open the trace for details, adjust the AOI or dates, and run again.";
  }
}

function readSearch(v: unknown): SearchInfo | null {
  const s = rec(v);
  if (!s) return null;
  const bboxRaw = Array.isArray(s.bbox) ? s.bbox.map(num) : null;
  const bbox =
    bboxRaw && bboxRaw.length === 4 && bboxRaw.every((x) => x !== null)
      ? (bboxRaw as [number, number, number, number])
      : null;
  const rw = rec(s.requested_window);
  const attempts = Array.isArray(s.attempts)
    ? s.attempts
        .map((a) => rec(a))
        .filter((a): a is Rec => a !== null)
        .map((a) => ({
          start: str(a.start) ?? "",
          end: str(a.end) ?? "",
          results: num(a.results) ?? 0,
          error: str(a.error),
        }))
    : [];
  return {
    bbox,
    sensors: strList(s.sensors),
    requestedWindow: rw && str(rw.start) && str(rw.end) ? { start: str(rw.start)!, end: str(rw.end)! } : null,
    attempts,
    widened: s.widened === true,
  };
}

function readEvidence(graph: unknown): EvidenceRow[] {
  const g = rec(graph);
  const nodes = rec(g?.nodes);
  if (!nodes) return [];
  return Object.entries(nodes).flatMap(([id, raw]) => {
    const n = rec(raw);
    if (!n) return [];
    const type = str(n.node_type) ?? "NODE";
    const data = rec(n.data) ?? {};
    const source = str(n.source) ?? "—";
    const confidence = n.confidence === null ? null : num(n.confidence);
    let title = source;
    let detail = "";
    if (type === "OBSERVATION") {
      title = `${str(data.sensor) ?? "Sensor"} scene`;
      detail = [str(data.asset_id), str(data.datetime)].filter(Boolean).join(" · ");
    } else if (type === "INFERENCE") {
      title = `Water segmentation · ${str(source.split(":")[0]) ?? source}`;
      const km2 = num(data.inundated_sqkm);
      const basis = str(data.confidence_basis);
      detail = [km2 !== null ? `${km2.toFixed(2)} km² water` : null, basis ? `confidence: ${basis}` : null]
        .filter(Boolean)
        .join(" · ");
    } else if (type === "METRIC") {
      const name = str(data.metric_name) ?? "metric";
      const value = num(data.value);
      const unit = str(data.unit) ?? "";
      title = name.replace(/_/g, " ");
      detail = value !== null ? `${value.toFixed(3)} ${unit}`.trim() : "—";
    }
    return [{ id, type, title, detail, source, confidence }];
  });
}

export function toLiveResult(state: MissionState): LiveResult {
  const status = (state.status ?? "").toUpperCase();
  const out = rec(state.synthesized_output) ?? {};
  const meta = rec(state.metadata) ?? {};
  const conf = rec(out.confidence) ?? rec(meta.confidence) ?? {};
  const inputs = rec(conf.inputs) ?? {};
  const inf = rec(out.inference) ?? rec(meta.inference_summary) ?? {};

  const observations = Array.isArray(meta.observations) ? meta.observations.map(rec) : [];
  const selectedId = str(out.observation_id) ?? str(meta.selected_observation_id);
  const selected = observations.find((o) => o && str(o.observation_id) === selectedId) ?? null;
  const scene = rec(selected?.scene) ?? {};

  const why = Object.entries(rec(out.why_explanation) ?? {})
    .map(([key, v]) => ({ key, title: WHY_TITLES[key] ?? key.replace(/_/g, " "), text: str(v) ?? "" }))
    .filter((w) => w.text);

  const failed = status === "FAILED";
  const reason = str(out.failure_reason);
  const summary = str(out.summary);
  const errors = strList(state.errors);

  return {
    status: status === "COMPLETED" ? "COMPLETED" : failed ? "FAILED" : "RUNNING",
    summary: failed ? null : summary,
    failure: failed
      ? {
          reason,
          text: summary ?? (errors.length ? errors.join("; ") : null),
          hint: failureHint(reason),
        }
      : null,
    areaKm2: failed ? null : num(out.inundation_area_sqkm),
    scene: {
      id: selectedId,
      acquiredAt: str(out.acquired_at) ?? str(scene.acquired_at),
      sensor: str(out.primary_sensor),
      collection: str(scene.collection),
      platform: str(scene.platform),
      coverage: num(meta.selected_scene_coverage),
    },
    confidence: {
      score: failed ? null : num(conf.score) ?? num(state.confidence_score),
      passedGate: typeof conf.passed_gate === "boolean" ? conf.passed_gate : null,
      modelConfidence: conf.model_confidence === null ? null : num(conf.model_confidence),
      modelBasis: str(conf.model_confidence_basis),
      scoreBasis: str(conf.score_basis),
      resolutionM: num(inputs.resolution_m),
      lagDays: num(inputs.temporal_lag_days),
    },
    why,
    uncertainty: strList(state.uncertainty_reasons ?? out.uncertainty_reasons),
    caveats: strList(inf.caveats).filter((c) => !c.startsWith("produced by ")),
    inference: {
      traceId: str(inf.trace_id),
      geometryRef: str(inf.geometry_ref),
      degradedFrom: str(inf.degraded_from),
      producedBy: str(inf.produced_by),
    },
    search: readSearch(out.search ?? meta.search),
    evidence: readEvidence(state.evidence_graph),
    citations: Array.isArray(out.citations) ? out.citations.length : 0,
  };
}

/** Square kilometres → hectares, for the result card (1 km² = 100 ha). */
export function km2ToHa(km2: number): number {
  return km2 * 100;
}

/**
 * Per-step detail lines from a (possibly partial) run state, so the step list
 * says what each node actually did — counts, the scene, the score — instead of
 * a generic description. Only fields that exist are used.
 */
export function liveStepDetails(state: MissionState | null): Partial<Record<string, string>> {
  if (!state) return {};
  const meta = rec(state.metadata) ?? {};
  const details: Partial<Record<string, string>> = {};

  const intent = rec(state.intent);
  const hazard = str(intent?.disaster_type);
  if (hazard) details.plan = `Hazard: ${hazard}.`;

  const decision = rec(meta.sensor_decision);
  const primary = str(decision?.primary);
  if (primary) details.sensor = `${primary.replace("_", " ")} selected.`;

  const search = readSearch(meta.search);
  const observations = Array.isArray(meta.observations) ? meta.observations.length : null;
  if (search && search.attempts.length) {
    const last = search.attempts[search.attempts.length - 1]!;
    const window = `${last.start.slice(0, 10)} → ${last.end.slice(0, 10)}`;
    details.search =
      observations !== null
        ? `${observations} scene(s) in ${window}${search.widened ? " (widened from 90 days)" : ""}.`
        : `Searched ${window}.`;
  }
  const selected = str(meta.selected_observation_id);
  if (selected && details.search) details.search += ` Using ${selected}.`;

  const conf = rec(meta.confidence);
  const score = num(conf?.score);
  if (score !== null) details.gate = `Score ${score.toFixed(2)}${conf?.passed_gate === false ? " (below gate)" : ""}.`;

  const io = rec(meta.inference_outcome);
  if (io?.outcome === "analysed") {
    const m = Array.isArray(io.measurements) ? rec(io.measurements[0]) : null;
    const ha = num(m?.value);
    const unit = str(m?.unit) ?? "ha";
    if (ha !== null) {
      const km2 = unit.startsWith("ha") ? ha / 100 : ha;
      details.analyse = `${km2.toFixed(2)} km² of water measured${io.degraded_from ? " (baseline method)" : ""}.`;
    }
  } else if (io?.outcome === "abstained") {
    details.analyse = `Abstained: ${str(io.explanation) ?? str(io.reason) ?? "no reason given"}.`;
  }
  return details;
}
