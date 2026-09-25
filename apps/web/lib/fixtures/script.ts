/**
 * The deterministic run script (P5-04, P5-17).
 *
 * Nine stages with fixed dwell times. The demo advances on a timer so the timeline
 * animates, but the *content* of every stage is constant and the sequence never
 * varies, so a Playwright assertion on "stage 6 says X" holds on every run.
 *
 * This drives the demo only. A live run's timeline is built from the job states the
 * gateway actually reports; it never uses these dwell times, because showing
 * invented progress for real backend work is the thing the PRD forbids most
 * explicitly ("Never show fake progress for real backend operations").
 */

import type { StageState } from "../model/console";

export type { StageState };

export interface RunStage {
  key: string;
  label: string;
  detail: string;
  /** Milliseconds this stage stays `running` before completing. */
  dwellMs: number;
  /** Terminal state. `degraded` is a real outcome, not a failure. */
  settlesTo: Exclude<StageState, "queued" | "running">;
}

export const DEMO_STAGES: readonly RunStage[] = [
  {
    key: "QUERY",
    label: "Query received",
    detail: "Natural-language request accepted and sanitized.",
    dwellMs: 700,
    settlesTo: "completed",
  },
  {
    key: "AOI",
    label: "AOI validated",
    detail: "26.2 km² polygon inside the analysis budget; geometry well-formed.",
    dwellMs: 600,
    settlesTo: "completed",
  },
  {
    key: "SENSOR",
    label: "Sensor arbitrated",
    detail: "Sentinel-2 cloud-obscured; Sentinel-1 selected as primary.",
    dwellMs: 900,
    settlesTo: "completed",
  },
  {
    key: "OBSERVE",
    label: "Observations selected",
    detail: "One Sentinel-1 acquisition; 46% of the AOI inside the swath.",
    dwellMs: 800,
    // Degraded, not completed: over half the AOI could not be analysed, and the
    // timeline should say so rather than showing a clean tick.
    settlesTo: "degraded",
  },
  {
    key: "PREPROCESS",
    label: "Preprocessing",
    detail: "Calibration, speckle handling, reprojection to EPSG:4326.",
    dwellMs: 1100,
    settlesTo: "completed",
  },
  {
    key: "INFERENCE",
    label: "Inference",
    detail: "hand-only-v2 — 3-channel U-Net with permanent-water prior.",
    dwellMs: 1400,
    settlesTo: "completed",
  },
  {
    key: "CHANGE",
    label: "Change detected",
    detail: "3.54 km² of new water across 17 polygons above the mapping unit.",
    dwellMs: 900,
    settlesTo: "completed",
  },
  {
    key: "EVIDENCE",
    label: "Evidence assembled",
    detail: "Seven nodes linked; one field unavailable and marked.",
    dwellMs: 700,
    settlesTo: "completed",
  },
  {
    key: "MONITOR",
    label: "Monitoring active",
    detail: "Armed at a 12-hour interval over the same AOI.",
    dwellMs: 600,
    settlesTo: "completed",
  },
] as const;

/** Total demo runtime, for the E2E timeout budget. */
export const DEMO_TOTAL_MS = DEMO_STAGES.reduce((sum, s) => sum + s.dwellMs, 0);
