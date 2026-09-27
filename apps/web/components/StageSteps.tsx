"use client";

/**
 * StageSteps — the mission run's pipeline steps as a JellyRadio strip.
 *
 * Same live data as the vertical run timeline (useMissionRun → Stage[]), but
 * presented as a horizontal segmented control: pick a step to read what the
 * backend actually reported for it. Nothing here invents progress — the radio
 * only browses stages that exist, and the status chip copies the timeline's
 * state colours, so a queued step cannot masquerade as a done one.
 *
 * Selection follows the run (the newest stage that is no longer queued) until
 * the user pins a step by clicking; pinning survives stage updates so the
 * reader can hold a step while the run advances. A new run (first stage key
 * changes) clears the pin.
 */

import { useEffect, useMemo, useState } from "react";

import JellyRadio from "./jelly/JellyRadio";
import type { Stage } from "../lib/types";

const STATUS_COLOR: Record<Stage["status"], string> = {
  done: "var(--accent, #c8f77a)",
  active: "var(--blue, #76aaf7)",
  warning: "var(--warn, #e5b55c)",
  error: "var(--danger, #ff827b)",
  pending: "var(--muted, #8e998d)",
};

const STATUS_WORD: Record<Stage["status"], string> = {
  done: "COMPLETED",
  active: "RUNNING",
  warning: "DEGRADED",
  error: "FAILED",
  pending: "QUEUED",
};

export default function StageSteps({ stages }: { stages: Stage[] }) {
  const [pinned, setPinned] = useState<number | null>(null);

  // The newest stage the run has actually reached.
  const activeIndex = useMemo(
    () => stages.reduce((acc, s, i) => (s.status !== "pending" ? i : acc), 0),
    [stages],
  );

  // A new run changes the first stage's identity — clear the stale pin.
  const firstKey = stages[0]?.key;
  useEffect(() => {
    setPinned(null);
  }, [firstKey]);

  // When the run reaches its final stage, release the pin so the strip lands
  // on the outcome. While the run is still moving, a pin holds.
  const lastStatus = stages[stages.length - 1]?.status;
  useEffect(() => {
    if (lastStatus && lastStatus !== "pending" && lastStatus !== "active") {
      setPinned(null);
    }
  }, [lastStatus]);

  const current =
    pinned !== null && pinned < stages.length ? pinned : activeIndex;
  const stage = stages[Math.min(current, Math.max(stages.length - 1, 0))];

  if (stages.length === 0 || !stage) {
    return (
      <section className="card timeline-card">
        <div className="card-head">
          <div>
            <div className="card-title">MISSION RUN · STEPS</div>
            <div className="card-sub">Auditable execution trace, step by step</div>
          </div>
          <span className="mono-chip">LIVE TRACE</span>
        </div>
        <p className="card-sub" style={{ margin: 0 }}>
          No stage has been reported yet. The backend drives this list —
          nothing is shown before it exists.
        </p>
      </section>
    );
  }

  return (
    <section className="card timeline-card">
      <div className="card-head">
        <div>
          <div className="card-title">MISSION RUN · STEPS</div>
          <div className="card-sub">Auditable execution trace, step by step</div>
        </div>
        <span className="mono-chip">LIVE TRACE</span>
      </div>

      <JellyRadio
        items={stages.map((s, i) => ({
          value: s.key,
          label: `${String(i + 1).padStart(2, "0")} ${s.label}`,
        }))}
        value={stage.key}
        onChange={(_, i) => setPinned(i)}
        size="sm"
        gap={6}
        radius={14}
        swell={0.12}
        barge={4}
        shrink={0.04}
        jelly={1}
        bounce={0.25}
        stagger={22}
        stiffness={580}
        ariaLabel="Mission run steps"
        className="stage-steps-radio"
      />

      <div className="stage-steps-detail" role="status">
        <div className="stage-steps-head">
          <span
            className="stage-dot"
            style={{ background: STATUS_COLOR[stage.status] }}
            aria-hidden="true"
          />
          <b>{stage.label}</b>
          <span className="mono-chip">{STATUS_WORD[stage.status]}</span>
          {stage.time && <span className="mono-chip">{stage.time}</span>}
        </div>
        <p>{stage.detail || "No detail published for this stage."}</p>
      </div>
    </section>
  );
}
