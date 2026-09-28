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
    <section className="card stage-list-card">
      <div className="card-head">
        <div>
          <div className="card-title">MISSION RUN · STEPS</div>
          <div className="card-sub">Auditable execution trace, step by step</div>
        </div>
        <span className="row" style={{ gap: 6 }}>
          {stages.length > 0 ? (
            <span
              className="mono-chip"
              aria-label={`${settled} of ${stages.length} steps settled`}
            >
              {settled}/{stages.length}
            </span>
          ) : null}
          <span className="mono-chip">LIVE TRACE</span>
        </span>
      </div>

      {stages.length === 0 ? (
        <p className="card-sub" style={{ margin: "6px 0 0" }}>
          No stage has been reported yet. The backend drives this list —
          nothing is shown before it exists.
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
