import type {
  ConfidenceRequest,
  ConfidenceResponse,
  ExecuteRequest as GenExecuteRequest,
  ExecuteResponse,
  HealthStatus,
  JobStatusResponse,
  JobSubmitResponse,
  MissionCreate,
  MissionListResponse,
  MissionResponse,
  MissionState as GenMissionState,
  MissionUpdate,
  PlanRequest as GenPlanRequest,
  PlanResponse,
  SensorDecisionRequest,
  SensorDecisionResponse,
} from "./generated";

export type {
  ConfidenceRequest,
  ConfidenceResponse,
  ExecuteResponse,
  HealthStatus,
  JobStatusResponse,
  JobSubmitResponse,
  MissionCreate,
  MissionListResponse,
  MissionResponse,
  MissionUpdate,
  PlanResponse,
  SensorDecisionRequest,
  SensorDecisionResponse,
};

export { MissionStatus } from "./generated";
export { JobStatus } from "./generated";

/* ── Shared & Overrides ───────────────────────────────────────────────────── */

export interface GeoJSONPolygon {
  type: "Polygon";
  /** [[[lon, lat], ...]] -- ring 0 is the exterior, wound counter-clockwise. */
  coordinates: number[][][];
}

export interface TemporalWindow {
  start: string;
  end: string;
}

/**
 * Override generated types to enforce strict GeoJSON shapes instead of Record<string, any>
 */
export interface PlanRequest extends Omit<GenPlanRequest, "aoi"> {
  aoi?: GeoJSONPolygon | null;
}

export interface ExecuteRequest extends Omit<GenExecuteRequest, "aoi" | "temporal_window"> {
  aoi?: GeoJSONPolygon | null;
  temporal_window?: TemporalWindow | null;
}

export interface MissionState extends Omit<GenMissionState, "aoi" | "temporal_window"> {
  aoi?: GeoJSONPolygon | null;
  temporal_window?: TemporalWindow | null;
}

export interface PlanStep {
  step_id: string;
  name: string;
  description: string;
  tool?: string | null;
  parameters?: Record<string, unknown>;
}

/**
 * Canonical error envelope (PRD section 5: "Canonical ErrorResponse: code, message,
 * details[], trace_id"). Every failure in the UI is rendered from one of these.
 */
export interface ErrorResponse {
  code: string;
  message: string;
  details?: unknown[];
  trace_id?: string | null;
}
