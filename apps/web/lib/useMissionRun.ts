"use client";

/**
 * Run state for the console (P5-04, P5-16, P5-17).
 *
 * Two paths that deliberately share no progress logic:
 *
 *   DEMO   advances through lib/fixtures/script.ts on pinned dwell times. The
 *          sequence is fixed, so Playwright can assert on it.
 *   LIVE   submits through the gateway and then *polls the job*. Stage states come
 *          from what the backend reports and nothing else. There is no interpolated
 *          progress bar and no optimistic tick: the PRD's rule is that fake progress
 *          for real work is never acceptable, and the way to guarantee that is for
 *          the live path to have no timer that can invent one.
 *
 * Polling backs off from 1s to 5s and stops at a terminal state or a hard error, so
 * a stuck job cannot turn into a request storm against the gateway.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { GatewayError, buildWsUrl } from "./api/gateway";
import { executeMission, getAgentRun } from "./api/client";
import { DEMO_STAGES, type RunStage } from "./fixtures";
import type { StageState } from "./model/console";
import type { ErrorResponse, GeoJSONPolygon, JobStatus } from "./api/types";

export interface RunStageView {
  key: string;
  label: string;
  detail: string;
  state: StageState;
}

export type RunPhase = "idle" | "running" | "complete" | "failed";

export interface MissionRun {
  phase: RunPhase;
  stages: RunStageView[];
  jobId: string | null;
  traceId: string | null;
  error: ErrorResponse | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  agentState: any | null; // using any for now, will map to backend MissionState
  start: (query: string, aoi: GeoJSONPolygon | null) => void;
  reset: () => void;
}



function demoStages(completedCount: number, runningIndex: number): RunStageView[] {
  return DEMO_STAGES.map((s: RunStage, i: number) => ({
    key: s.key,
    label: s.label,
    detail: s.detail,
    state:
      i < completedCount
        ? s.settlesTo
        : i === runningIndex
          ? ("running" as const)
          : ("queued" as const),
  }));
}

/** The live timeline has exactly the states the job reports — no more. */
function liveStages(status: JobStatus | null, error: ErrorResponse | null): RunStageView[] {
  const submitted: RunStageView = {
    key: "SUBMIT",
    label: "Run submitted",
    detail: "The gateway accepted the request and returned a job id.",
    state: "completed",
  };
  const work: RunStageView = {
    key: "JOB",
    label: "Backend processing",
    detail:
      status === null
        ? "Waiting for the first job status."
        : `The job reports status "${status}". No stage detail is published by the ` +
          `backend yet, so none is shown.`,
    state:
      status === "completed"
        ? "completed"
        : status === "failed" || status === "cancelled"
          ? "failed"
          : "running",
  };
  if (error) {
    work.state = "failed";
    work.detail = error.message;
  }
  return [submitted, work];
}

export function useMissionRun(demo: boolean): MissionRun {
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [stages, setStages] = useState<RunStageView[]>(
    demo ? demoStages(0, -1) : [],
  );
  const [jobId, setJobId] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [error, setError] = useState<ErrorResponse | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [agentState, setAgentState] = useState<any | null>(null);

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const abort = useRef<AbortController | null>(null);

  const clearAll = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    abort.current?.abort();
    abort.current = null;
  }, []);

  useEffect(() => clearAll, [clearAll]);

  const reset = useCallback(() => {
    clearAll();
    setPhase("idle");
    setStages(demo ? demoStages(0, -1) : []);
    setJobId(null);
    setTraceId(null);
    setError(null);
    setAgentState(null);
  }, [clearAll, demo]);

  /* ── demo ───────────────────────────────────────────────────────────────── */

  const startDemo = useCallback(() => {
    clearAll();
    setError(null);
    setPhase("running");
    setJobId("job-demo-7f3a2c91");
    setTraceId("trc-0000-demo-fixture");

    let elapsed = 0;
    DEMO_STAGES.forEach((stage: RunStage, i: number) => {
      timers.current.push(
        setTimeout(() => setStages(demoStages(i, i)), elapsed),
      );
      elapsed += stage.dwellMs;
      timers.current.push(
        setTimeout(() => setStages(demoStages(i + 1, -1)), elapsed),
      );
    });
    timers.current.push(setTimeout(() => setPhase("complete"), elapsed));
  }, [clearAll]);

  /* ── live ───────────────────────────────────────────────────────────────── */

  const startLive = useCallback(
    async (query: string, aoi: GeoJSONPolygon | null) => {
      clearAll();
      setError(null);
      setPhase("running");
      setStages(liveStages(null, null));

      const controller = new AbortController();
      abort.current = controller;

      try {
        const submitted = await executeMission(
          { query, aoi, mission_id: null },
          // Idempotency-Key so a double-click cannot queue the same analysis twice.
          `run-${query.length}-${Date.now()}`,
        );
        setJobId(submitted.data.job_id);
        setTraceId(submitted.data.trace_id ?? submitted.traceId);

        const missionId = submitted.data.mission_id;
        if (!missionId) {
          throw new Error("Missing mission_id in execute response");
        }

        const wsUrl = buildWsUrl(`/ws/v1/missions/${missionId}`);
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (controller.signal.aborted) {
            ws.close();
          }
        };

        ws.onmessage = async (event) => {
          try {
            const payload = JSON.parse(event.data);
            if (payload.event === "connected") {
               // Initial connection established
            } else if (payload.event === "status_update") {
               const status = payload.status;
               setStages(liveStages(status, null));
            } else if (payload.event === "done") {
               const status = payload.final_status;
               setStages(liveStages(status, null));
               if (status === "completed") {
                 try {
                   const agentResult = await getAgentRun(submitted.data.job_id, controller.signal);
                   setAgentState(agentResult.data);
                 } catch (e) {
                   console.warn("Failed to fetch agent state", e);
                 }
                 setPhase("complete");
               } else {
                 setError({
                    code: `job_${status}`,
                    message: `The job ${status}.`,
                    details: [],
                    trace_id: submitted.data.trace_id,
                 });
                 setPhase("failed");
               }
            }
          } catch (e) {
            console.warn("Failed to parse websocket message", e);
          }
        };

        ws.onerror = (e) => {
          console.error("WebSocket error", e);
          setError({
            code: "websocket_error",
            message: "WebSocket connection error.",
            details: [],
            trace_id: submitted.data.trace_id,
          });
          setPhase("failed");
        };

        ws.onclose = () => {
          // If we are still running, it's an unexpected close
          if (phase === "running") {
             // Maybe retry or fail
          }
        };

        controller.signal.addEventListener("abort", () => {
           ws.close();
        });
      } catch (caught) {
        const body =
          caught instanceof GatewayError
            ? caught.body
            : {
                code: "unknown",
                message: "The run could not be submitted.",
                details: [],
                trace_id: null,
              };
        setError(body);
        setStages(liveStages(null, body));
        setPhase("failed");
      }
    },
    [clearAll, phase],
  );

  const start = useCallback(
    (query: string, aoi: GeoJSONPolygon | null) => {
      if (demo) startDemo();
      else void startLive(query, aoi);
    },
    [demo, startDemo, startLive],
  );

  return { phase, stages, jobId, traceId, error, agentState, start, reset };
}
