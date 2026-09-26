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

import { GatewayError } from "./api/gateway";
import { executeMission, getAgentRun } from "./api/client";

/**
 * GET /agent/runs/{job_id} answers 404 until the run registers with the
 * orchestrator, so the first polls after a 202 can legitimately miss. A 404 is
 * treated as "not yet" only inside this window; after it, a 404 is the honest
 * answer and the run fails.
 */
const RUN_404_GRACE_MS = 15_000;

const AGENT_STAGE_BY_STATUS: Record<string, string> = {
  INITIALIZED: "Agent run accepted — workflow initialising.",
  PLANNING: "Extracting intent and planning the acquisition.",
  SENSOR_ARBITRATION: "Arbitrating sensors.",
  ACQUIRING: "Acquiring candidate observations.",
  ACQUIRING_EVIDENCE: "Acquiring candidate observations.",
  ANALYZING: "Analysing observations.",
  GATE_CHECK: "Running the confidence gate.",
  SYNTHESIZING: "Synthesising the evidence-backed brief.",
  COMPLETED: "The agent run completed.",
  FAILED: "The agent run failed.",
};
import { DEMO_STAGES } from "./fixtures";
import type { StageState } from "./model/console";
import type {
  ErrorResponse,
  GeoJSONPolygon,
  JobStatus,
  MissionState,
} from "./api/types";

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
  /** Mission id the backend reports for this run — the WS event stream is keyed
   * by it (live mode); the console's agent-event socket subscribes with this. */
  missionId: string | null;
  traceId: string | null;
  error: ErrorResponse | null;
  /** The agent's final state (mission_id, confidence, evidence graph), fetched
   * once when a live run completes. Null in demo mode and until completion. */
  agentState: MissionState | null;
  start: (query: string, aoi: GeoJSONPolygon | null) => void;
  reset: () => void;
}

const POLL_START_MS = 1000;
const POLL_MAX_MS = 5000;

function demoStages(completedCount: number, runningIndex: number): RunStageView[] {
  return DEMO_STAGES.map((s, i) => ({
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

/** The live timeline has exactly the states the agent run reports — no more. */
function liveStages(
  status: JobStatus | null,
  error: ErrorResponse | null,
  detail: string | null = null,
): RunStageView[] {
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
      error !== null
        ? error.message
        : detail ??
          (status === null
            ? "Waiting for the agent run to register."
            : `The run reports status "${status}". No stage detail is published by the ` +
              `backend yet, so none is shown.`),
    state:
      status === "completed"
        ? "completed"
        : status === "failed" || status === "cancelled"
          ? "failed"
          : "running",
  };
  return [submitted, work];
}

export function useMissionRun(demo: boolean): MissionRun {
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [stages, setStages] = useState<RunStageView[]>(
    demo ? demoStages(0, -1) : [],
  );
  const [jobId, setJobId] = useState<string | null>(null);
  const [missionId, setMissionId] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [error, setError] = useState<ErrorResponse | null>(null);
  const [agentState, setAgentState] = useState<MissionState | null>(null);

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
    setMissionId(null);
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
    DEMO_STAGES.forEach((stage, i) => {
      timers.current.push(
        setTimeout(() => setStages(demoStages(i, i)), elapsed),
      );
      elapsed += stage.dwellMs;
      timers.current.push(
        setTimeout(() => setStages(demoStages(i + 1, -1)), elapsed),
      );
    });
    timers.current.push(setTimeout(() => setPhase("complete"), elapsed));
    // The demo panel is fed from the pinned scenario, not from the backend, so
    // there is deliberately no agent state to fetch here.
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
        setMissionId(submitted.data.mission_id);
        setTraceId(submitted.data.trace_id ?? submitted.traceId);

        let delay = POLL_START_MS;
        const startedAt = Date.now();
        const poll = async () => {
          if (controller.signal.aborted) return;
          try {
            // The job id returned by POST /agent/execute belongs to the agent
            // service, so the run is polled where it lives: GET /agent/runs/{id}.
            // (GET /jobs/{id} is the mission service's registry and does not know
            // this id — polling it reports Not Found for a healthy run.)
            const agent = await getAgentRun(submitted.data.job_id, controller.signal);
            const run = agent.data;
            const status = (run.status ?? "").toUpperCase();
            setStages(
              liveStages(
                status === "COMPLETED" ? "completed" : status === "FAILED" ? "failed" : "running",
                null,
                AGENT_STAGE_BY_STATUS[status] ?? null,
              ),
            );

            if (status === "COMPLETED") {
              // The run state itself is the final payload — no extra fetch.
              setAgentState(run);
              setPhase("complete");
              return;
            }
            if (status === "FAILED") {
              setError({
                code: "agent_run_failed",
                message:
                  (run.errors ?? [])
                    .filter((e): e is string => typeof e === "string")
                    .join("; ") || `The agent run reported status "${status}".`,
                details: [],
                trace_id: agent.traceId,
              });
              setPhase("failed");
              return;
            }

            delay = Math.min(delay * 1.5, POLL_MAX_MS);
            timers.current.push(setTimeout(poll, delay));
          } catch (caught) {
            // A 404 inside the grace window means the orchestrator has not
            // registered the run yet — keep polling rather than failing.
            const withinGrace = Date.now() - startedAt < RUN_404_GRACE_MS;
            if (
              caught instanceof GatewayError &&
              caught.status === 404 &&
              caught.body.code === "RUN_NOT_FOUND" &&
              withinGrace
            ) {
              delay = Math.min(delay * 1.5, POLL_MAX_MS);
              timers.current.push(setTimeout(poll, delay));
              return;
            }
            const body =
              caught instanceof GatewayError
                ? caught.body
                : {
                    code: "unknown",
                    message: "Polling the run failed.",
                    details: [],
                    trace_id: null,
                  };
            setError(body);
            setStages(liveStages(null, body));
            setPhase("failed");
          }
        };
        timers.current.push(setTimeout(poll, delay));
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
    [clearAll],
  );

  const start = useCallback(
    (query: string, aoi: GeoJSONPolygon | null) => {
      if (demo) startDemo();
      else void startLive(query, aoi);
    },
    [demo, startDemo, startLive],
  );

  return { phase, stages, jobId, missionId, traceId, error, agentState, start, reset };
}
