"use client";

/**
 * Vertical mission-run step list, shown directly under the query input.
 * Order is the pipeline order (query received first); the step currently
 * being processed is highlighted. Same live data as everything else — no
 * invented progress.
 */

import { CircleCheck, CircleDashed, LoaderCircle, OctagonAlert, TriangleAlert } from "lucide-react";
import type { Stage } from "../lib/types";

const WORD: Record<Stage["status"], string> = {
  done: "COMPLETED",
  active: "RUNNING",
  warning: "DEGRADED",
  error: "FAILED",
  pending: "QUEUED",
};

export default function StageList({ stages }: { stages: Stage[] }) {
  // Counts steps that have reached an outcome (a degraded step has settled, it
  // just did not fully succeed). It is a tally of what was reported, not a
  // progress estimate.
  const settled = stages.filter(
    (s) => s.status === "done" || s.status === "warning",
  ).length;
  return (
    <section className="sqd-card stage-list-card" aria-label="Run steps">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">Steps</span>
        {stages.length > 0 ? (
          <span
            className="sqd-chip sqd-mono"
            aria-label={`${settled} of ${stages.length} steps settled`}
          >
            {settled}/{stages.length}
          </span>
        ) : null}
      </header>

      {stages.length === 0 ? (
        <p className="sqd-muted">
          Steps appear when a run starts; each one turns green only when the
          backend reports it finished.
        </p>
      ) : (
        <ol className="stage-list">
          {stages.map((s, i) => (
            <li
              key={s.key}
              className={`stage-list-row ${s.status} ${
                s.status === "active" || s.status === "warning" ? "is-current" : ""
              }`}
            >
              <span className="stage-list-icon">
                {s.status === "done" ? (
                  <CircleCheck size={15} />
                ) : s.status === "active" ? (
                  <LoaderCircle className="spin" size={15} />
                ) : s.status === "warning" ? (
                  <TriangleAlert size={15} />
                ) : s.status === "error" ? (
                  <OctagonAlert size={15} />
                ) : (
                  <CircleDashed size={15} />
                )}
              </span>
              <span className="stage-list-num">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="stage-list-body">
                <b>{s.label}</b>
                <small>{s.detail || WORD[s.status]}</small>
              </span>
              <span className="stage-list-state">{WORD[s.status]}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
