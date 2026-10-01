"use client";

/**
 * Run state for the console (P5-04, P5-16, P5-17; audit W1, W3, W4, W5, W9, W11).
 *
 * Two paths that deliberately share no progress logic:
 *
 *   DEMO   advances through lib/fixtures/script.ts on pinned dwell times. The
 *          sequence is fixed, so Playwright can assert on it.
 *   LIVE   gets a session, creates a mission (so the event socket can subscribe),
 *          submits through the gateway and then *polls the run*. Step states come
 *          from the statuses the agent persists after each graph node and nothing
 *          else: there is no interpolated progress and no optimistic tick.
 *
 * Polling backs off from 1s to 5s, stops at a terminal state or a hard error, and
 * gives up after RUN_DEADLINE_MS, so a lost run cannot spin forever.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { GatewayError } from "./api/gateway";
import { createMission, executeMission, getAgentRun } from "./api/client";
import { DEMO_STAGES } from "./fixtures";
import { buildLiveSteps, statusRank } from "./live/steps";
import { liveStepDetails } from "./live/result";
import { dropSession, ensureSession, isGatewayDown, type SessionState } from "./live/session";
import type { StageState } from "./model/console";
import type { ErrorResponse, GeoJSONPolygon, MissionState, TemporalWindow } from "./api/types";

/**
 * GET /agent/runs/{job_id} can answer 404 for a moment after the 202 when the
 * run is stored in another process. Inside this window a 404 means "not yet".
 */
const RUN_404_GRACE_MS = 15_000;

/** A live run that has not finished after this long is reported as timed out. */
export const RUN_DEADLINE_MS = 6 * 60_000;

const POLL_START_MS = 1000;
const POLL_MAX_MS = 5000;

export interface RunStageView {
  key: string;
  label: string;
  detail: string;
  state: StageState;
}

export type RunPhase = "idle" | "running" | "complete" | "failed";

/** Why a live run ended in "failed", so the UI can show the right card. */
export type FailureKind =
  | "agent" // the agent finished with status FAILED (its reason is in agentState)
  | "gateway-down" // the gateway did not answer
  | "auth" // no usable credential
  | "timeout" // the run did not finish before RUN_DEADLINE_MS
  | "request"; // the gateway refused the request (4xx/5xx with an envelope)

export interface MissionRun {
  phase: RunPhase;
  stages: RunStageView[];
  jobId: string | null;
  /** Mission id the run is attached to; the event socket subscribes with it. */
  missionId: string | null;
  traceId: string | null;
  error: ErrorResponse | null;
  failureKind: FailureKind | null;
  /** Latest run state from the agent: updated while running, kept on FAILED. */
  agentState: MissionState | null;
  session: SessionState | null;
  start: (query: string, aoi: GeoJSONPolygon | null, window?: TemporalWindow | null) => void;
  reset: () => void;
}

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

function envelope(caught: unknown, fallback: string): ErrorResponse {
  return caught instanceof GatewayError
    ? caught.body
    : { code: "unknown", message: fallback, details: [], trace_id: null };
}

export function useMissionRun(demo: boolean): MissionRun {
  const [phase, setPhase] = useState<RunPhase>("idle");
  const [stages, setStages] = useState<RunStageView[]>(demo ? demoStages(0, -1) : []);
  const [jobId, setJobId] = useState<string | null>(null);
  const [missionId, setMissionId] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [error, setError] = useState<ErrorResponse | null>(null);
  const [failureKind, setFailureKind] = useState<FailureKind | null>(null);
  const [agentState, setAgentState] = useState<MissionState | null>(null);
  const [session, setSession] = useState<SessionState | null>(null);

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
    setFailureKind(null);
    setAgentState(null);
  }, [clearAll, demo]);

  /* ── demo ───────────────────────────────────────────────────────────────── */

  const startDemo = useCallback(() => {
    clearAll();
    setError(null);
    setFailureKind(null);
    setPhase("running");
    setJobId("job-demo-7f3a2c91");
    setTraceId("trc-0000-demo-fixture");

    let elapsed = 0;
    DEMO_STAGES.forEach((stage, i) => {
      timers.current.push(setTimeout(() => setStages(demoStages(i, i)), elapsed));
      elapsed += stage.dwellMs;
      timers.current.push(setTimeout(() => setStages(demoStages(i + 1, -1)), elapsed));
    });
    timers.current.push(setTimeout(() => setPhase("complete"), elapsed));
    // The demo panel is fed from the pinned scenario, not from the backend, so
    // there is deliberately no agent state to fetch here.
  }, [clearAll]);

  /* ── live ───────────────────────────────────────────────────────────────── */

  const startLive = useCallback(
    async (query: string, aoi: GeoJSONPolygon | null, window: TemporalWindow | null) => {
      clearAll();
      setError(null);
      setFailureKind(null);
      setAgentState(null);
      setJobId(null);
      setMissionId(null);
      setTraceId(null);
      setPhase("running");
      setStages(buildLiveSteps({ furthest: null, terminal: null }));

      const controller = new AbortController();
      abort.current = controller;

      const fail = (kind: FailureKind, body: ErrorResponse, furthest: string | null, state: MissionState | null) => {
        if (controller.signal.aborted) return;
        setError(body);
        setFailureKind(kind);
        setStages(
          buildLiveSteps({
            furthest,
            terminal: kind === "agent" ? "FAILED" : null,
            transportFailed: kind !== "agent",
            failureReason:
              kind === "agent"
                ? ((state?.synthesized_output as Record<string, unknown> | null)?.failure_reason as string | undefined)
                : null,
            failureText: body.message,
            details: liveStepDetails(state),
          }),
        );
        setPhase("failed");
      };

      // 1. A credential (audit W1).
      let sess = await ensureSession(controller.signal);
      if (controller.signal.aborted) return;
      setSession(sess);
      if (sess.kind === "gateway-down") {
        fail("gateway-down", { code: "network_unreachable", message: sess.message, details: [], trace_id: null }, null, null);
        return;
      }
      if (sess.kind === "needs-credential") {
        fail("auth", { code: "AUTH_REQUIRED", message: sess.message, details: [], trace_id: null }, null, null);
        return;
      }

      // 2. A mission to run against, so the event socket can subscribe (audit
      //    W9). Best-effort: without the mission service the run still works,
      //    it just has no live agent pop-ups.
      let mission: string | null = null;
      try {
        const created = await createMission(
          {
            name: `Live analysis · ${new Date().toISOString().slice(0, 16).replace("T", " ")} UTC`,
            description: query.slice(0, 500),
          },
          `mission-${Date.now()}`,
        );
        mission = created.data.id;
      } catch {
        mission = null;
      }
      if (controller.signal.aborted) return;

      // 3. Submit. One re-authentication on 401 (an expired dev token).
      const submit = () =>
        executeMission(
          { query, aoi, mission_id: mission, temporal_window: window ?? null },
          // Idempotency-Key so a double-click cannot queue the same analysis twice.
          `run-${query.length}-${Date.now()}`,
        );
      let submitted;
      try {
        try {
          submitted = await submit();
        } catch (caught) {
          if (caught instanceof GatewayError && caught.status === 401) {
            dropSession();
            sess = await ensureSession(controller.signal);
            setSession(sess);
            if (sess.kind !== "ready") throw caught;
            submitted = await submit();
          } else {
            throw caught;
          }
        }
      } catch (caught) {
        const body = envelope(caught, "The run could not be submitted.");
        const kind: FailureKind =
          caught instanceof GatewayError && isGatewayDown(caught)
            ? "gateway-down"
            : caught instanceof GatewayError && caught.status === 401
              ? "auth"
              : "request";
        fail(kind, body, null, null);
        return;
      }
      if (controller.signal.aborted) return;

      const job = submitted.data.job_id;
      setJobId(job);
      setMissionId(submitted.data.mission_id ?? mission);
      setTraceId(submitted.data.trace_id ?? submitted.traceId);

      // 4. Poll the run where it lives: GET /agent/runs/{job_id}.
      let delay = POLL_START_MS;
      const startedAt = Date.now();
      let furthest: string | null = "INITIALIZED";
      let latest: MissionState | null = null;
      let reauthed = false;

      setStages(buildLiveSteps({ furthest, terminal: null }));

      const poll = async () => {
        if (controller.signal.aborted) return;
        if (Date.now() - startedAt > RUN_DEADLINE_MS) {
          fail(
            "timeout",
            {
              code: "RUN_TIMEOUT",
              message: `The run did not finish within ${RUN_DEADLINE_MS / 60_000} minutes. It may still be running on the server.`,
              details: [],
              trace_id: submitted.traceId,
            },
            furthest,
            latest,
          );
          return;
        }
        try {
          const agent = await getAgentRun(job, controller.signal);
          const run = agent.data;
          latest = run;
          const status = (run.status ?? "").toUpperCase();
          if (statusRank(status) > (furthest ? statusRank(furthest) : -1)) furthest = status;
          setAgentState(run);

          if (status === "COMPLETED") {
            setStages(
              buildLiveSteps({ furthest: "COMPLETED", terminal: "COMPLETED", details: liveStepDetails(run) }),
            );
            setPhase("complete");
            return;
          }
          // A node that cannot continue writes FAILED, but the graph still runs on
          // to synthesize, which records the reason. FAILED is terminal only once
          // that answer (or a crash error) is there; until then keep polling.
          const finalFailure =
            status === "FAILED" &&
            (run.synthesized_output != null || (run.errors ?? []).length > 0);
          if (finalFailure) {
            const out = (run.synthesized_output ?? {}) as Record<string, unknown>;
            const summary = typeof out.summary === "string" ? out.summary : null;
            const errs = (run.errors ?? []).filter((e): e is string => typeof e === "string");
            fail(
              "agent",
              {
                code: typeof out.failure_reason === "string" ? out.failure_reason : "agent_run_failed",
                message: summary ?? (errs.join("; ") || "The agent run failed without a reason."),
                details: [],
                trace_id: agent.traceId,
              },
              furthest,
              run,
            );
            return;
          }

          setStages(buildLiveSteps({ furthest, terminal: null, details: liveStepDetails(run) }));
          delay = Math.min(delay * 1.5, POLL_MAX_MS);
          timers.current.push(setTimeout(poll, delay));
        } catch (caught) {
          if (controller.signal.aborted) return;
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
          if (caught instanceof GatewayError && caught.status === 401 && !reauthed) {
            reauthed = true;
            dropSession();
            const again = await ensureSession(controller.signal);
            setSession(again);
            if (again.kind === "ready") {
              timers.current.push(setTimeout(poll, POLL_START_MS));
              return;
            }
          }
          const body = envelope(caught, "Polling the run failed.");
          const kind: FailureKind =
            caught instanceof GatewayError && isGatewayDown(caught)
              ? "gateway-down"
              : caught instanceof GatewayError && caught.status === 401
                ? "auth"
                : "request";
          fail(kind, body, furthest, latest);
        }
      };
      timers.current.push(setTimeout(poll, delay));
    },
    [clearAll],
  );

  const start = useCallback(
    (query: string, aoi: GeoJSONPolygon | null, window: TemporalWindow | null = null) => {
      if (demo) startDemo();
      else void startLive(query, aoi, window);
    },
    [demo, startDemo, startLive],
  );

  return {
    phase,
    stages,
    jobId,
    missionId,
    traceId,
    error,
    failureKind,
    agentState,
    session,
    start,
    reset,
  };
}
