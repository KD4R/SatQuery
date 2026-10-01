/**
 * The live run's step list, one row per agent graph node (audit W4).
 *
 * The statuses are the ones services/agent/graph/orchestrator.py writes into
 * MissionState.status as each node finishes; the run is persisted after every
 * node, so polling GET /agent/runs/{job_id} walks through them in order:
 *
 *   INITIALIZED → PLANNING → ARBITRATING → ACQUIRING → ANALYZING → GATE_CHECK
 *     (→ REINVESTIGATE → ARBITRATING → … once, when the gate asks for another scene)
 *   → COMPLETED | FAILED
 *
 * If the orchestrator renames a status, the step simply stays "queued" and the
 * unit tests in steps.test.ts fail — nothing here invents progress.
 */

import type { StageState } from "../model/console";

export interface LiveStep {
  key: string;
  label: string;
  /** Status values that mean this step has finished. */
  doneWhen: readonly string[];
  /** What the step does, shown while it is queued or running. */
  idle: string;
}

export const LIVE_STEPS: readonly LiveStep[] = [
  { key: "submit", label: "Run accepted", doneWhen: ["INITIALIZED"], idle: "Sending the query, AOI and dates to the gateway." },
  { key: "plan", label: "Understand the question", doneWhen: ["PLANNING"], idle: "Extracting the hazard and objectives from the query." },
  { key: "sensor", label: "Choose the sensor", doneWhen: ["ARBITRATING"], idle: "Picking the satellite sensor that can answer it." },
  { key: "search", label: "Find imagery", doneWhen: ["ACQUIRING"], idle: "Searching Planetary Computer for scenes over the AOI." },
  { key: "analyse", label: "Measure water", doneWhen: ["ANALYZING"], idle: "Reading the scene window and segmenting water." },
  { key: "gate", label: "Confidence gate", doneWhen: ["GATE_CHECK", "REINVESTIGATE"], idle: "Scoring the evidence before anything is reported." },
  { key: "answer", label: "Write the answer", doneWhen: ["COMPLETED"], idle: "Building the summary and WHY from the evidence." },
] as const;

/** Order of statuses, for "how far did the run get". */
const STATUS_ORDER = [
  "INITIALIZED",
  "PLANNING",
  "ARBITRATING",
  "ACQUIRING",
  "ANALYZING",
  "GATE_CHECK",
  "REINVESTIGATE",
  "COMPLETED",
];

export function statusRank(status: string): number {
  const i = STATUS_ORDER.indexOf(status.toUpperCase());
  return i === -1 ? -1 : i;
}

/** Which step a failure reason belongs to (from synthesized_output.failure_reason). */
export function failedStepFor(reason: string | null | undefined): string | null {
  if (!reason) return null;
  const r = reason.toUpperCase();
  if (
    r.startsWith("AOI_") ||
    r === "INVALID_TEMPORAL_WINDOW" ||
    r === "NO_SCENES_IN_WINDOW" ||
    r === "NO_ANALYSABLE_SCENE" ||
    r === "CATALOGUE_UNAVAILABLE"
  )
    return "search";
  if (r === "LOW_CONFIDENCE") return "gate";
  if (r === "SYNTHESIS_FAILED" || r === "NO_EVIDENCE") return "answer";
  // Inference abstentions and INFERENCE_UNAVAILABLE
  return "analyse";
}

export interface StepView {
  key: string;
  label: string;
  detail: string;
  state: StageState;
}

/**
 * Build the step rows from the furthest status seen and the terminal outcome.
 *
 * `furthest` is the highest-ranked status observed while polling (a fast run can
 * skip past statuses between polls; those steps are still done). `terminal` is
 * "COMPLETED", "FAILED" or null while running. `transportFailed` marks the run as
 * failed at the point it had reached, when the gateway itself stopped answering.
 */
export function buildLiveSteps(args: {
  furthest: string | null;
  terminal: "COMPLETED" | "FAILED" | null;
  failureReason?: string | null;
  failureText?: string | null;
  transportFailed?: boolean;
  details?: Partial<Record<string, string>>;
}): StepView[] {
  const { furthest, terminal, failureReason, failureText, transportFailed, details = {} } = args;
  const reached = furthest ? statusRank(furthest) : -1;
  const failedKey =
    terminal === "FAILED" || transportFailed
      ? (failedStepFor(failureReason) ??
        // No reason: fail the first step that had not finished.
        LIVE_STEPS.find((s) => !s.doneWhen.some((d) => statusRank(d) <= reached))?.key ??
        "answer")
      : null;

  let failedSeen = false;
  return LIVE_STEPS.map((step) => {
    const done =
      terminal === "COMPLETED" ||
      step.doneWhen.some((d) => statusRank(d) !== -1 && statusRank(d) <= reached);
    let state: StageState;
    let detail = details[step.key] ?? step.idle;
    if (failedKey === step.key) {
      state = "failed";
      failedSeen = true;
      detail = failureText ?? detail;
    } else if (failedSeen) {
      state = "queued";
      detail = "Not reached.";
    } else if (done) {
      state = "completed";
    } else if (terminal === null && !transportFailed) {
      // The first unfinished step is the one running.
      const firstOpen = LIVE_STEPS.find(
        (s) => !s.doneWhen.some((d) => statusRank(d) !== -1 && statusRank(d) <= reached),
      );
      state = firstOpen?.key === step.key ? "running" : "queued";
    } else {
      state = "queued";
    }
    return { key: step.key, label: step.label, detail, state };
  });
}
