/**
 * The demo's agent-activity feed (P5 Phase C, PRD §2C).
 *
 * The live console learns what the agent is doing from the mission WebSocket;
 * the demo has no socket, so its feed replays the *same narratives* the
 * orchestrator emits, on the run script's schedule. The strings are the fixed
 * server-side templates from services/agent/events/stream.py and
 * graph/orchestrator.py — the demo and a live run say identical things, which
 * is the point: the demo exists to show exactly what a real mission shows.
 *
 * `atMs` values are offsets into the run (total ~7.7 s; stages are
 * 700/600/900/800/1100/1400/900/700/600 ms), chosen to land mid-stage and
 * strictly before completion — an event scheduled after the run ends would
 * never fire:
 *   1000  SENSOR stage  → disagreement + acquiring (PRD's example toast)
 *   2700  PREPROCESS    → the extra radar pass arrives
 *   5400  INFERENCE end → arbitration resolves
 *   6600  EVIDENCE      → agent thought as the panel assembles
 *
 * Deterministic like the rest of lib/fixtures: offsets, clocks, prose —
 * everything pinned, nothing from Date.now (P5-17).
 */

import type { AgentEvent } from "../ws/useMissionEvents";

interface DemoAgentEvent {
  atMs: number;
  type: AgentEvent["type"];
  message: string;
}

export const DEMO_AGENT_EVENTS: readonly DemoAgentEvent[] = [
  {
    atMs: 1000,
    type: "SENSOR_DISAGREEMENT",
    message:
      "Optical and SAR disagree on flood extent — acquiring an additional radar observation to arbitrate.",
  },
  {
    atMs: 1150,
    type: "ACQUIRING_EVIDENCE",
    message: "Selecting the observations that cover the area of interest.",
  },
  {
    atMs: 2700,
    type: "ACQUIRING_EVIDENCE",
    message: "Additional radar pass found; adding it to the evidence set.",
  },
  {
    atMs: 5400,
    type: "SENSOR_AGREEMENT",
    message: "Sensors agree on the observed extent; no extra acquisition needed.",
  },
  {
    atMs: 6600,
    type: "AGENT_THOUGHT",
    message: "Water segmentation complete; the confidence gate runs next.",
  },
] as const;

/**
 * Builds the toast views the console feeds AgentActivityToasts. Clocks are
 * pinned to the fixture epoch so the demo renders identically every run; the
 * wall-clock time a toast actually appeared is irrelevant to what it says.
 */
export function demoEventAt(e: DemoAgentEvent, i: number): AgentEvent {
  const minute = String(42 + i).padStart(2, "0");
  return {
    id: `demo-evt-${i + 1}`,
    type: e.type,
    message: e.message,
    at: `2026-09-14T05:${minute}:00.000Z`,
  };
}
