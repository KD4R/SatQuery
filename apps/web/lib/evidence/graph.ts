/**
 * The evidence chain, as data (P5-09 → PRD §2B).
 *
 * The WHY panel lists what was considered; the graph shows how the conclusion was
 * actually reached. This module is the pure layer between the ConsoleScenario view
 * model and a React Flow node/edge graph. It holds no React and no rendering, so it
 * can be tested without a DOM and reused by the report screen later.
 *
 * Honesty rules carry over from the rest of P5: a node the backend could not fill
 * is rendered unavailable, never quietly dropped, and a gate that was not passed is
 * shown as below the gate — a graph that always ends in a green node is a diagram
 * of a lie.
 */

import type { ConsoleScenario } from "../model/console";
import type { EvidenceNode } from "../model/console";

/* ── Graph view model ─────────────────────────────────────────────────────── */

export type EvidenceGraphNodeKind =
  | "insight"
  | "gate"
  | "model"
  | "observation"
  | "sensor"
  | "context";

/** Visual + semantic metadata for one node in the chain.
 *
 *  A type alias, not an interface: React Flow v12 requires node data to be
 *  assignable to Record<string, unknown>, and only type aliases get TypeScript's
 *  implicit index signature.
 */
export type EvidenceGraphNode = {
  id: string;
  kind: EvidenceGraphNodeKind;
  /** Short title on the node card. */
  label: string;
  /** One-line substance. Null renders as NOT AVAILABLE on the card. */
  value: string | null;
  /** Shown when `value` is null, explaining the gap. */
  reason?: string;
  /** Where this came from — dataset, service, report. */
  provenance: string | null;
  /** 0..1 when the node carries a score the operator can weigh. */
  score: number | null;
}

export interface EvidenceGraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  /** The primary path to the conclusion, drawn heavier. */
  primary?: boolean;
}

export interface EvidenceGraph {
  nodes: EvidenceGraphNode[];
  edges: EvidenceGraphEdge[];
  /** The insight node id — the graph's entry point. */
  rootId: string;
  /** Whether the confidence gate was passed (colors the path honestly). */
  passedGate: boolean;
}

/* ── Builder ──────────────────────────────────────────────────────────────── */

/**
 * Builds the WHY chain for the scenario's headline change detection:
 *
 *   Insight → Confidence Gate → Model → Sensor read → Observation → Context
 *
 * Sensor nodes derive from `scenario.arbitration` (SAR/or optical, with their own
 * scores); observation nodes from `scenario.evidence`; the model node from the
 * inference provenance. Edges always exist (insight→gate→model), so the chain is
 * never disconnected even when the backend supplies nothing.
 */
export function buildEvidenceGraph(scenario: ConsoleScenario): EvidenceGraph {
  const nodes: EvidenceGraphNode[] = [];
  const edges: EvidenceGraphEdge[] = [];

  const headline = scenario.change.headline;
  const rootId = "node-insight";
  nodes.push({
    id: rootId,
    kind: "insight",
    label: "Insight",
    value: `${headline} — ${scenario.change.areaSqKm.toFixed(2)} km² in ${String(
      scenario.change.polygonCount,
    )} polygons`,
    provenance: `trace ${scenario.traceId}`,
    score: null,
  });

  const gateId = "node-gate";
  nodes.push({
    id: gateId,
    kind: "gate",
    label: "Confidence gate",
    value:
      scenario.confidence.uncertaintyFactors.length > 0
        ? `${scenario.confidence.uncertaintyFactors.length} uncertainty factors held the score down`
        : null,
    reason: "No uncertainty factors were reported for this run.",
    provenance: "agent confidence gate",
    score: scenario.confidence.score,
  });
  edges.push({
    id: "edge-insight-gate",
    source: rootId,
    target: gateId,
    label: "claims",
    primary: true,
  });

  const modelId = "node-model";
  nodes.push({
    id: modelId,
    kind: "model",
    label: "Model",
    value: scenario.modelVersion
      ? `${scenario.modelVersion} — trained segmentation model`
      : null,
    reason: "The inference service did not report a model version.",
    provenance: scenario.modelVersion
      ? "inference service · model registry"
      : null,
    score: null,
  });
  edges.push({
    id: "edge-gate-model",
    source: gateId,
    target: modelId,
    label: "produced",
    primary: true,
  });

  // One node per sensor reading — SAR and/or optical — each with its own score.
  for (const reading of scenario.arbitration.readings) {
    const sensorId = `node-sensor-${reading.sensor.toLowerCase().replace(/\W+/g, "-")}`;
    nodes.push({
      id: sensorId,
      kind: "sensor",
      label: reading.sensor,
      value: reading.note,
      provenance: `agent sensor arbitration · finding: ${reading.finding}`,
      score: reading.confidence,
    });
    edges.push({
      id: `edge-model-${sensorId}`,
      source: modelId,
      target: sensorId,
      label:
        reading.sensor === scenario.arbitration.primary ? "primary sensor" : "corroborating",
      primary: reading.sensor === scenario.arbitration.primary,
    });
  }

  // Observation nodes from the evidence chain, excluding duplicates of what the
  // sensor and gate nodes already carry.
  const seenValues = new Set(
    nodes.map((n) => n.value ?? "").filter((v) => v.length > 0),
  );
  for (const ev of scenario.evidence) {
    if (ev.value === null) {
      // The not-available evidence row stays in the graph: the gap is information.
      const naId = `node-evidence-${ev.id}`;
      nodes.push({
        id: naId,
        kind: kindForEvidence(ev.kind),
        label: ev.label,
        value: null,
        reason: ev.reason,
        provenance: ev.provenance,
        score: null,
      });
      edges.push({
        id: `edge-evidence-${ev.id}`,
        source: modelId,
        target: naId,
      });
      continue;
    }
    if (seenValues.has(ev.value)) continue;
    seenValues.add(ev.value);
    const id = `node-evidence-${ev.id}`;
    nodes.push({
      id,
      kind: kindForEvidence(ev.kind),
      label: ev.label,
      value: ev.value,
      provenance: ev.provenance,
      score: null,
    });
    edges.push({
      id: `edge-evidence-${ev.id}`,
      source: modelId,
      target: id,
    });
  }

  // AOI context grounds the whole chain in where this was measured.
  const aoiId = "node-aoi";
  nodes.push({
    id: aoiId,
    kind: "context",
    label: "AOI",
    value: `${scenario.aoiName} · ${scenario.aoiAreaSqKm.toFixed(1)} km²`,
    provenance: `coverage ${Math.round(scenario.change.coverageFraction * 100)}% of the AOI was analysed`,
    score: null,
  });
  edges.push({
    id: "edge-aoi-model",
    source: modelId,
    target: aoiId,
    label: "measured in",
  });

  return {
    nodes,
    edges,
    rootId,
    passedGate: scenario.confidence.passedGate,
  };
}

function kindForEvidence(kind: EvidenceNode["kind"]): EvidenceGraphNodeKind {
  switch (kind) {
    case "observation":
    case "comparison":
      return "observation";
    case "sensor":
      return "sensor";
    case "model":
      return "model";
    default:
      return "context";
  }
}
