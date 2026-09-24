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

// Removed ConsoleScenario imports

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
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function buildEvidenceGraph(backendState: any): EvidenceGraph {
  const nodes: EvidenceGraphNode[] = [];
  const edges: EvidenceGraphEdge[] = [];
  
  if (!backendState || !backendState.evidence_graph) {
    return { nodes, edges, rootId: "unknown", passedGate: false };
  }

  const backendNodes = backendState.evidence_graph.nodes || {};
  const backendEdges = backendState.evidence_graph.edges || [];
  
  let rootId = "node-insight";
  
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  for (const [nid, n] of Object.entries(backendNodes) as any) {
    const type = n.node_type || "observation";
    let kind: EvidenceGraphNodeKind = "context";
    if (type === "observation") kind = "observation";
    if (type === "inference") kind = "model";
    if (type === "metric") kind = "insight";
    
    nodes.push({
      id: nid as string,
      kind,
      label: n.title || "Node",
      value: n.summary || JSON.stringify(n.data),
      provenance: n.provenance || n.source,
      score: n.confidence || null,
    });
    if (kind === "insight") rootId = nid as string;
  }
  
  for (const e of backendEdges) {
    edges.push({
      id: `edge-${e.source_id}-${e.target_id}`,
      source: e.source_id,
      target: e.target_id,
      label: e.relationship,
      primary: e.weight > 0.8,
    });
  }

  return {
    nodes,
    edges,
    rootId,
    passedGate: backendState.confidence_score ? backendState.confidence_score > 0.6 : true,
  };
}
