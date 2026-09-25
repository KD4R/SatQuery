"use client";

/**
 * The WHY graph (PRD §2B) — the evidence chain as a node graph, not a list.
 *
 * Insight → Confidence Gate → Model → Sensor reads → Observations → AOI context.
 * Data comes from lib/evidence/graph.ts; this file only lays it out and keeps the
 * interactions honest:
 *
 *   - React Flow is loaded client-side only and only when the drawer opens, so the
 *     console's first-load budget is untouched until an operator asks for it.
 *   - A node whose value the backend did not supply renders NOT AVAILABLE on the
 *     card — a gap is information, the same rule the WHY list follows.
 *   - Text is rendered as text (A03). Nothing from the backend ever becomes HTML.
 */

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useReducedMotion } from "framer-motion";
import { useMemo } from "react";

import type {
  EvidenceGraph,
  EvidenceGraphNode,
} from "../../lib/evidence/graph";

/** React Flow's typed node: `data` is the evidence node itself. */
type EvidenceFlowNode = Node<EvidenceGraphNode, "evidence">;

/* ── Node card ────────────────────────────────────────────────────────────── */

const KIND_GLYPH: Record<EvidenceGraphNode["kind"], string> = {
  insight: "★",
  gate: "◆",
  model: "▣",
  observation: "◇",
  sensor: "◉",
  context: "▭",
};

function EvidenceNodeCard({ data }: NodeProps<EvidenceFlowNode>) {
  const node = data;
  return (
    <div className={`egraph-card egraph-card-${node.kind}`}>
      <Handle type="target" position={Position.Left} className="egraph-handle" />
      <div className="egraph-card-head">
        <span className="egraph-glyph" aria-hidden="true">
          {KIND_GLYPH[node.kind]}
        </span>
        <span className="label">{node.label}</span>
        {node.score !== null ? (
          <span
            className={`mono egraph-score ${
              node.score >= 0.75 ? "sig" : node.score >= 0.5 ? "amb" : "faint"
            }`}
          >
            {node.score.toFixed(2)}
          </span>
        ) : null}
      </div>
      {node.value ? (
        <p className="egraph-value">{node.value}</p>
      ) : (
        <p
          className="readout-value readout-value-na"
          title={node.reason ?? "Not supplied by the backend."}
        >
          NOT AVAILABLE
        </p>
      )}
      {node.provenance ? <p className="egraph-prov">{node.provenance}</p> : null}
      <Handle type="source" position={Position.Right} className="egraph-handle" />
    </div>
  );
}

const NODE_TYPES = { evidence: EvidenceNodeCard };

/* ── Layout ───────────────────────────────────────────────────────────────── */

/**
 * Column-per-kind layout, computed here rather than by a dagre dependency: the
 * chain shape is known (insight → gate → model → {sensors, observations, context}),
 * so a fixed lattice is deterministic, testable, and free.
 */
function layout(graph: EvidenceGraph): EvidenceFlowNode[] {
  const columns: Record<string, number> = {
    insight: 0,
    gate: 1,
    model: 2,
    sensor: 3,
    observation: 3,
    context: 3,
  };
  const COLUMN_X: Record<number, number> = { 0: 0, 1: 260, 2: 520, 3: 780 };
  const perColumn = new Map<number, EvidenceGraphNode[]>();
  for (const n of graph.nodes) {
    const col = columns[n.kind] ?? 3;
    const list = perColumn.get(col) ?? [];
    list.push(n);
    perColumn.set(col, list);
  }

  const nodes: EvidenceFlowNode[] = [];
  for (const [col, list] of perColumn) {
    list.forEach((n, i) => {
      nodes.push({
        id: n.id,
        type: "evidence",
        position: { x: COLUMN_X[col], y: i * 96 },
        data: n,
        draggable: false,
        selectable: true,
      });
    });
  }
  return nodes;
}

function toFlowEdges(graph: EvidenceGraph): Edge[] {
  return graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.label,
    animated: !graph.passedGate && e.primary,
    className: e.primary ? "egraph-edge egraph-edge-primary" : "egraph-edge",
    style: e.primary
      ? { stroke: "var(--signal)", strokeWidth: 1.6 }
      : { stroke: "var(--hairline-bright)", strokeWidth: 1 },
    labelStyle: { fill: "var(--ink-dim)", fontSize: 9 },
    labelBgStyle: { fill: "var(--surface-2)" },
  }));
}

/* ── Drawer ───────────────────────────────────────────────────────────────── */

function GraphFallback() {
  return (
    <div className="egraph-loading">
      <span className="label label-faint">Loading evidence graph…</span>
    </div>
  );
}

export function EvidenceGraphDrawer({
  graph,
  open,
  onClose,
  loading = false,
}: {
  graph: EvidenceGraph | null;
  open: boolean;
  onClose: () => void;
  loading?: boolean;
}) {
  const reduce = useReducedMotion();

  const nodes = useMemo(() => (graph ? layout(graph) : []), [graph]);
  const edges = useMemo(() => (graph ? toFlowEdges(graph) : []), [graph]);

  if (!open) return null;

  return (
    <div
      className="egraph-drawer"
      role="dialog"
      aria-modal="true"
      aria-label="Evidence graph"
    >
      <div className="egraph-drawer-head">
        <span className="label">Why this was flagged — evidence chain</span>
        <div className="band-spacer" />
        <button type="button" className="btn btn-icon" onClick={onClose} aria-label="Close evidence graph">
          ✕
        </button>
      </div>
      <div className="egraph-canvas" style={{ opacity: reduce ? 1 : undefined }}>
        {loading || !graph ? (
          <GraphFallback />
        ) : (
          <ReactFlow<EvidenceFlowNode, Edge>
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
            minZoom={0.4}
            maxZoom={1.6}
            proOptions={{ hideAttribution: true }}
            nodesConnectable={false}
            edgesFocusable={false}
            preventScrolling={false}
          >
            <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--hairline)" />
            <Controls showInteractive={false} className="egraph-controls" />
          </ReactFlow>
        )}
      </div>
      <div className="egraph-legend">
        <span>★ insight</span>
        <span>◆ gate {graph?.passedGate ? "· above" : "· BELOW"}</span>
        <span>▣ model</span>
        <span>◉ sensor</span>
        <span>◇ observation</span>
        <span>▭ context</span>
      </div>
    </div>
  );
}

export default EvidenceGraphDrawer;
