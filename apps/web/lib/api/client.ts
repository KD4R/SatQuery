/**
 * Typed calls over the eleven gateway routes (P5-02).
 *
 * One function per route, named for the operation, returning the DTO transcribed in
 * types.ts. Nothing here knows about React; nothing here knows about fixtures.
 */

import { buildPath, GATEWAY_ROUTES } from "./routes";
import { request, type GatewayResult } from "./gateway";
import type {
  ConfidenceRequest,
  ConfidenceResponse,
  ExecuteRequest,
  ExecuteResponse,
  HealthStatus,
  JobStatusResponse,
  JobSubmitResponse,
  MissionCreate,
  MissionResponse,
  MissionState,
  PlanRequest,
  PlanResponse,
  SensorDecisionRequest,
  SensorDecisionResponse,
} from "./types";

/* ── System ───────────────────────────────────────────────────────────────── */

export function getHealth(signal?: AbortSignal): Promise<GatewayResult<HealthStatus>> {
  return request<HealthStatus>(GATEWAY_ROUTES.health, { signal, timeoutMs: 4000 });
}

/* ── Missions (P5-12) ─────────────────────────────────────────────────────── */

/**
 * The gateway declares this response as an untyped proxy passthrough, so the shape
 * is whatever the mission service sends. It sends either a bare array or
 * MissionListResponse depending on version; both are accepted and normalised here
 * rather than at eleven call sites.
 */
export async function listMissions(
  signal?: AbortSignal,
): Promise<GatewayResult<MissionResponse[]>> {
  const result = await request<MissionResponse[] | { items?: MissionResponse[] }>(
    GATEWAY_ROUTES.missions,
    { signal },
  );
  const raw = result.data;
  const items = Array.isArray(raw) ? raw : (raw?.items ?? []);
  return { ...result, data: items };
}

export function getMission(
  missionId: string,
  signal?: AbortSignal,
): Promise<GatewayResult<MissionResponse>> {
  return request<MissionResponse>(
    buildPath(GATEWAY_ROUTES.mission, { mission_id: missionId }),
    { signal },
  );
}

export function createMission(
  body: MissionCreate,
  idempotencyKey?: string,
): Promise<GatewayResult<MissionResponse>> {
  return request<MissionResponse>(GATEWAY_ROUTES.missions, {
    method: "POST",
    body,
    idempotencyKey,
  });
}

/** HTTP 202 -- long-running work returns a job id, never a result (PRD section 5). */
export function submitRun(
  missionId: string,
  idempotencyKey?: string,
): Promise<GatewayResult<JobSubmitResponse>> {
  return request<JobSubmitResponse>(
    buildPath(GATEWAY_ROUTES.missionRuns, { mission_id: missionId }),
    { method: "POST", idempotencyKey },
  );
}

/* ── Jobs (P5-04) ─────────────────────────────────────────────────────────── */

export function getJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<GatewayResult<JobStatusResponse>> {
  return request<JobStatusResponse>(
    buildPath(GATEWAY_ROUTES.job, { job_id: jobId }),
    { signal, timeoutMs: 8000 },
  );
}

/* ── Agent (P5-03, P5-10, P5-11) ──────────────────────────────────────────── */

export function planMission(
  body: PlanRequest,
  signal?: AbortSignal,
): Promise<GatewayResult<PlanResponse>> {
  return request<PlanResponse>(GATEWAY_ROUTES.agentPlan, {
    method: "POST",
    body,
    signal,
    timeoutMs: 20_000,
  });
}

export function executeMission(
  body: ExecuteRequest,
  idempotencyKey?: string,
): Promise<GatewayResult<ExecuteResponse>> {
  return request<ExecuteResponse>(GATEWAY_ROUTES.agentExecute, {
    method: "POST",
    body,
    idempotencyKey,
  });
}

export function getAgentRun(
  jobId: string,
  signal?: AbortSignal,
): Promise<GatewayResult<MissionState>> {
  return request<MissionState>(
    buildPath(GATEWAY_ROUTES.agentRun, { job_id: jobId }),
    { signal },
  );
}

export function scoreConfidence(
  body: ConfidenceRequest,
  signal?: AbortSignal,
): Promise<GatewayResult<ConfidenceResponse>> {
  return request<ConfidenceResponse>(GATEWAY_ROUTES.agentConfidence, {
    method: "POST",
    body,
    signal,
  });
}

export function decideSensor(
  body: SensorDecisionRequest,
  signal?: AbortSignal,
): Promise<GatewayResult<SensorDecisionResponse>> {
  return request<SensorDecisionResponse>(GATEWAY_ROUTES.agentSensorDecision, {
    method: "POST",
    body,
    signal,
  });
}

export function listTools(
  signal?: AbortSignal,
): Promise<GatewayResult<{ tools?: unknown[] }>> {
  return request<{ tools?: unknown[] }>(GATEWAY_ROUTES.agentTools, { signal });
}
