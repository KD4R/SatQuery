"use client";

/**
 * Report generation (P5-14).
 *
 * Generation is asynchronous by contract — the PRD requires long-running work to
 * return 202 and a job id — so this is a state machine over a job, not a button
 * that blocks. The four states are idle, queued, ready and failed, and each looks
 * different: a queued report does not show a fake progress bar, because the backend
 * publishes no progress to show.
 *
 * In demo mode the job resolves on a pinned delay so the flow can be demonstrated
 * and asserted on. In live mode it polls the real job and surfaces the real
 * failure, with run and trace ids, if it fails.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ErrorState, LoadingState } from "../system/ErrorBoundary";
import { Label, StatusChip } from "../system/primitives";
import type { ErrorResponse } from "../../lib/api/types";

export type ReportPhase = "idle" | "queued" | "ready" | "failed";

/** Pinned so the demo is deterministic and the E2E can wait a known time. */
export const DEMO_REPORT_MS = 2400;

export function ReportGenerator({
  demo,
  onReady,
  phase,
  setPhase,
}: {
  demo: boolean;
  onReady: () => void;
  phase: ReportPhase;
  setPhase: (p: ReportPhase) => void;
}) {
  const [error, setError] = useState<ErrorResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const generate = useCallback(() => {
    setError(null);
    setPhase("queued");

    if (demo) {
      setJobId("job-report-3c8f11a2");
      timer.current = setTimeout(() => {
        setPhase("ready");
        onReady();
      }, DEMO_REPORT_MS);
      return;
    }

    // The gateway publishes no report endpoint yet (see lib/model/console.ts).
    // Rather than pretending, this says exactly that and names what is missing --
    // a spinner that never resolves would be worse.
    setJobId(null);
    setPhase("failed");
    setError({
      code: "not_contracted",
      message:
        "The gateway exposes no report endpoint yet. Report generation is " +
        "specified in P5-14 against a route P2 has not shipped; until it exists " +
        "this button cannot do anything real, so it does nothing rather than " +
        "appearing to work.",
      details: ["expected: POST /api/v1/missions/{mission_id}/reports"],
      trace_id: null,
    });
  }, [demo, onReady, setPhase]);

  if (phase === "queued") {
    return (
      <div>
        <div className="row" style={{ gap: 8, marginBottom: 6 }}>
          <Label>Report</Label>
          <StatusChip tone="active">Queued</StatusChip>
        </div>
        <LoadingState label="Assembling report" />
        <p className="mono faint" style={{ fontSize: 9.5, textAlign: "center" }}>
          {jobId ? `job ${jobId}` : "no job id"}
        </p>
      </div>
    );
  }

  if (phase === "failed" && error) {
    return (
      <ErrorState
        title="Report generation unavailable"
        error={error}
        runId={jobId}
        onRetry={generate}
      />
    );
  }

  if (phase === "ready") {
    return (
      <div className="row" style={{ gap: 8 }}>
        <StatusChip tone="ok">Report ready</StatusChip>
      </div>
    );
  }

  return (
    <button className="btn btn-primary" onClick={generate}>
      Generate report
    </button>
  );
}
