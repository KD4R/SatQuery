/**
 * Shared UI types for the SatQuery dashboard (P5).
 *
 * Reconstructed single source of truth: several components under
 * `components/` import these, but the module was missing from the repo,
 * which broke `next build` (and therefore the web Docker image).
 */

/** Lifecycle state of one pipeline stage in the mission run timeline. */
export type StageStatus = "done" | "active" | "warning" | "error" | "pending";

/** One pipeline stage shown in the run timeline and trace drawer. */
export interface Stage {
  /** Short uppercase stage key, e.g. "PARSE", "RESOLVE", "DISCOVER". */
  key: string;
  /** Human-readable headline for the stage. */
  label: string;
  /** Longer explanation of what happened in this stage. */
  detail: string;
  /** Current lifecycle state (drives timeline iconography). */
  status: StageStatus;
  /** Optional wall-clock timestamp, e.g. "11:39". */
  time?: string;
}

/** Provenance-tracked evidence item rendered in the evidence panel. */
export interface Evidence {
  id: string;
  kind: "observation" | "decision" | string;
  title: string;
  source: string;
  detail: string;
  status: "verified" | "pending" | string;
  /** Dataset / processing reference for audit. */
  provenance: string;
}

/** Arbitration decision between optical and SAR modalities. */
export interface MissionDecision {
  winner: "SAR" | "optical" | string;
  reason: string;
  optical: string;
  sar: string;
}

/** Aggregate dashboard state for one mission run. */
export interface MissionState {
  missionId: string;
  runId: string;
  status: string;
  query: string;
  location: string;
  aoiArea: string;
  /** Model confidence in [0, 1]. */
  confidence: number;
  stages: Stage[];
  observations: unknown[];
  evidence: Evidence[];
  decision: MissionDecision;
  summary: string;
}
