"use client";

/**
 * The run timeline (P5-04).
 *
 * Built on the numbered gutter from the reference film: a fixed ruler of line
 * numbers with content on the lines that have any. The empty numerals carry real
 * information — they show the length of the whole run, so four completed stages
 * read as "four of nine" rather than as a list that happens to have four rows.
 *
 * Two rules this component exists to enforce:
 *
 *   1. `degraded` is a first-class outcome, distinct from both completed and
 *      failed. A stage that finished having analysed 46% of the AOI is not a green
 *      tick, and pretending otherwise is how a demo ends up overclaiming.
 *   2. No stage shows progress that was not reported. For a live run the states
 *      come from the job the gateway returns; the animated dwell times belong to
 *      the demo script only.
 */

import { motion, useReducedMotion } from "framer-motion";

import { NumberedGutter, Panel, StatusChip } from "../system/primitives";
import type { StageState } from "../../lib/model/console";

export interface TimelineStage {
  key: string;
  label: string;
  detail: string;
  state: StageState;
}

const GLYPH: Record<StageState, string> = {
  queued: "·",
  running: "▸",
  completed: "✓",
  degraded: "▲",
  failed: "✕",
};

export interface MissionTimelineProps {
  stages: TimelineStage[];
  /** Ruler length. Defaults to the stage count; pass more to show the full run. */
  lines?: number;
}

export function MissionTimeline({ stages, lines }: MissionTimelineProps) {
  const reduce = useReducedMotion();
  const total = lines ?? Math.max(stages.length, 12);

  const done = stages.filter(
    (s) => s.state === "completed" || s.state === "degraded",
  ).length;
  const failed = stages.some((s) => s.state === "failed");
  const degraded = stages.some((s) => s.state === "degraded");

  const rows = new Map(
    stages.map((stage, i) => [
      i + 1,
      <StageRow key={stage.key} stage={stage} reduce={Boolean(reduce)} />,
    ]),
  );

  return (
    <Panel
      title="Run timeline"
      actions={
        <StatusChip tone={failed ? "warn" : degraded ? "warn" : done === stages.length ? "ok" : "active"}>
          {done}/{stages.length}
        </StatusChip>
      }
    >
      <div style={{ padding: "6px 8px 10px" }}>
        <NumberedGutter lines={total} rows={rows} />
      </div>
    </Panel>
  );
}

function StageRow({ stage, reduce }: { stage: TimelineStage; reduce: boolean }) {
  const colour =
    stage.state === "running"
      ? "var(--signal)"
      : stage.state === "degraded" || stage.state === "failed"
        ? "var(--amber)"
        : stage.state === "completed"
          ? "var(--ink)"
          : "var(--ink-ghost)";

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 3 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.12, ease: [0.2, 0, 0.1, 1] }}
    >
      <div className="row" style={{ gap: 7, alignItems: "baseline" }}>
        <span
          className="mono"
          style={{ color: colour, width: 10, fontSize: 10 }}
          aria-hidden="true"
        >
          {GLYPH[stage.state]}
        </span>
        <span
          className="label"
          style={{ color: colour, letterSpacing: "0.1em", fontSize: 9.5 }}
        >
          {stage.key}
        </span>
        <span
          style={{
            fontSize: 11.5,
            color: stage.state === "queued" ? "var(--ink-ghost)" : "var(--ink)",
          }}
        >
          {stage.label}
        </span>
        <div className="band-spacer" />
        {stage.state === "degraded" ? (
          <StatusChip tone="warn" title={stage.detail}>
            degraded
          </StatusChip>
        ) : stage.state === "failed" ? (
          <StatusChip tone="warn">failed</StatusChip>
        ) : null}
        <span className="sr-only">{stage.state}</span>
      </div>
      {stage.state !== "queued" ? (
        <p
          className="mono"
          style={{
            margin: "1px 0 0 17px",
            fontSize: 10,
            color: "var(--ink-faint)",
            lineHeight: 1.4,
          }}
        >
          {stage.detail}
        </p>
      ) : null}
    </motion.div>
  );
}
