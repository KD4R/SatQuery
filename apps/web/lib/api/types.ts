/**
 * Gateway DTOs (P5-02).
 *
 * WHY THESE ARE HAND-WRITTEN, NOT GENERATED
 * -----------------------------------------
 * The gateway is a transparent proxy: every request and response body in
 * docs/openapi/gateway.json is typed `"schema": {}`. Codegen against it therefore
 * yields a route table and no models -- which is exactly what the committed client
 * under packages/contracts/generated/ts/ contains (one model: HealthStatus).
 *
 * The real shapes are published by the two services behind the proxy, in
 * docs/openapi/mission.json and docs/openapi/agent.json. These interfaces are
 * transcribed from those specs. Each carries the spec and schema name it came from
 * so drift is traceable by hand, and lib/api/routes.ts is checked against
 * gateway.json by a test so route drift is caught automatically.
 *
 * Regenerate-by-hand procedure is documented in apps/web/lib/api/README.md.
 */

/* ── mission.json ─────────────────────────────────────────────────────────── */

/** mission.json # MissionStatus */
export type MissionStatus =
  | "draft"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/** mission.json # JobStatus */
export type JobStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

/** mission.json # MissionCreate */
export interface MissionCreate {
  name: string;
  description?: string | null;
  aoi_ids?: string[];
}

/** mission.json # MissionResponse */
export interface MissionResponse {
  id: string;
  name: string;
  description: string | null;
  status: MissionStatus;
  aoi_ids: string[];
  organisation_id: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/** mission.json # MissionListResponse */
export interface MissionListResponse {
  items: MissionResponse[];
  total?: number;
}

/** mission.json # AOICreate */
export interface AOICreate {
  name: string;
  description?: string | null;
  /** GeoJSON geometry. Validated client-side by lib/geo/validate.ts before send. */
  geometry: GeoJSONPolygon;
}

/** mission.json # AOIResponse */
export interface AOIResponse {
  id: string;
  name: string;
  description: string | null;
  geometry: GeoJSONPolygon;
  organisation_id: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/** mission.json # JobSubmitResponse (HTTP 202) */
export interface JobSubmitResponse {
  job_id: string;
  mission_id: string;
  status: JobStatus;
  submitted_at: string;
  trace_id: string | null;
  message?: string;
}

/** mission.json # JobStatusResponse */
export interface JobStatusResponse {
  job_id: string;
  mission_id: string;
  status: JobStatus;
  submitted_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  trace_id: string | null;
}

/* ── agent.json ───────────────────────────────────────────────────────────── */

/** agent.json # PlanStep */
export interface PlanStep {
  step_id: string;
  name: string;
  description: string;
  tool?: string | null;
  parameters?: Record<string, unknown>;
}

/** agent.json # PlanRequest */
export interface PlanRequest {
  query: string;
  mission_id?: string | null;
  aoi?: GeoJSONPolygon | null;
  metadata?: Record<string, unknown>;
}

/** agent.json # PlanResponse */
export interface PlanResponse {
  mission_id: string;
  intent: Record<string, unknown>;
  plan_steps: PlanStep[];
  selected_sensors: string[];
  trace_id?: string | null;
}

/** agent.json # ExecuteRequest */
export interface ExecuteRequest {
  query: string;
  mission_id?: string | null;
  aoi?: GeoJSONPolygon | null;
  temporal_window?: TemporalWindow | null;
  budget?: Record<string, unknown> | null;
}

/** agent.json # ExecuteResponse (HTTP 202) */
export interface ExecuteResponse {
  job_id: string;
  mission_id: string;
  status: string;
  message: string;
  trace_id?: string | null;
}

/** agent.json # ConfidenceRequest */
export interface ConfidenceRequest {
  evidence_nodes?: unknown[];
  sensor_type?: string;
  cloud_cover?: number;
  resolution_meters?: number;
}

/** agent.json # ConfidenceResponse */
export interface ConfidenceResponse {
  confidence_score: number;
  passed_gate: boolean;
  uncertainty_factors?: string[];
  action: string;
  trace_id?: string | null;
}

/** agent.json # SensorDecisionRequest */
export interface SensorDecisionRequest {
  hazard_type?: string;
  cloud_cover_percentage?: number;
  is_night?: boolean;
  priority?: string;
}

/** agent.json # SensorDecisionResponse */
export interface SensorDecisionResponse {
  primary_sensor: string;
  secondary_sensor?: string | null;
  rationale: string;
  arbitration_score: number;
  trace_id?: string | null;
}

/**
 * agent.json # MissionState
 *
 * The spine of the console. Everything the intelligence panel renders hangs off
 * this object. Fields the agent has not populated stay null/empty and render as
 * NOT AVAILABLE rather than being filled in by the UI.
 */
export interface MissionState {
  mission_id: string;
  run_id: string;
  organization_id: string;
  job_id?: string | null;
  trace_id?: string | null;
  query: string;
  sanitized_query?: string | null;
  status?: string;
  intent?: Record<string, unknown> | null;
  aoi?: GeoJSONPolygon | null;
  temporal_window?: TemporalWindow | null;
  selected_sensors?: string[];
  observation_ids?: string[];
  tool_calls?: unknown[];
  evidence_graph?: Record<string, unknown> | null;
  confidence_score?: number;
  uncertainty_reasons?: string[];
  synthesized_output?: Record<string, unknown> | null;
  errors?: unknown[];
  metadata?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

/** gateway.json # HealthStatus */
export interface HealthStatus {
  status: string;
  service: string;
}

/* ── Shared ───────────────────────────────────────────────────────────────── */

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
 * Canonical error envelope (PRD section 5: "Canonical ErrorResponse: code, message,
 * details[], trace_id"). Every failure in the UI is rendered from one of these.
 */
export interface ErrorResponse {
  code: string;
  message: string;
  details?: unknown[];
  trace_id?: string | null;
}

/* ── inference.json (P3, reached through the gateway) ─────────────────────── */

/** inference.json # ConfidenceBasis */
export type ConfidenceBasis = "model_agreement" | "calibrated_probability" | "not_calibrated";

/**
 * inference.json # Confidence
 *
 * `value` is null whenever `basis` is not_calibrated -- the backend contract rejects
 * anything else. The UI must render that as NOT AVAILABLE with the caveats, never
 * as 0% and never as a guessed number.
 */
export interface InferenceConfidence {
  basis: ConfidenceBasis;
  /** Decimal serialised as a string by pydantic, or null. */
  value: string | null;
  interval: [string, string] | null;
  calibration_ref: string | null;
  agreement_iou: string | null;
  caveats: string[];
}

/** inference.json # MeasurementUnit */
export type MeasurementUnit = "ha" | "km2" | "m" | "km" | "count" | "fraction";

/** inference.json # Measurement */
export interface Measurement {
  name: string;
  /** Decimal serialised as a string. */
  value: string;
  unit: MeasurementUnit;
  produced_by: string;
  code_version: string;
  crs: string;
  derived_from: InferenceSceneRef[];
}

/** inference.json # Provider */
export type Provider =
  | "asf_hyp3"
  | "copernicus_dataspace"
  | "planetary_computer"
  | "bhoonidhi"
  | "sen1floods11"
  | "senforflood";

/** inference.json # SceneRef */
export interface InferenceSceneRef {
  provider: Provider;
  collection: string;
  item_id: string;
  acquired_at: string;
  platform: string;
  instrument: string;
  relative_orbit: number | null;
  pass_direction: string | null;
  href: string;
  cloud_cover?: number | null;
}

/** inference.json # AnalysisRequest */
export interface InferenceAnalysisRequest {
  scene: InferenceSceneRef;
  scene_href: string;
  permanent_water_href?: string | null;
  model?: string | null;
  min_mapping_unit_ha?: number;
}

/** inference.json # Analysis */
export interface InferenceAnalysis {
  outcome: "analysed";
  measurements: Measurement[];
  /** Storage key. Draw it via GET /inference/analyses/{trace_id}/extent. */
  geometry_ref: string | null;
  raster_refs: string[];
  confidence: InferenceConfidence | null;
  scenes: InferenceSceneRef[];
  /** Set when a fallback produced this. The UI must show it. */
  degraded_from: string | null;
  caveats: string[];
  trace_id: string;
}

/** inference.json # AbstentionReason */
export type AbstentionReason =
  | "no_scenes_in_window"
  | "cloud_exceeds_threshold"
  | "sensor_cannot_answer"
  | "orbit_mismatch"
  | "aoi_outside_coverage"
  | "product_offline"
  | "models_disagree"
  | "aoi_too_large"
  | "input_failed_preflight"
  | "no_separable_threshold";

/** inference.json # Abstention */
export interface InferenceAbstention {
  outcome: "abstained";
  reason: AbstentionReason;
  explanation: string;
  nearest_usable: InferenceSceneRef | null;
  scenes_seen: InferenceSceneRef[];
  trace_id: string;
}

/** The analysis endpoint returns one or the other, both with HTTP 200. */
export type InferenceOutcome = InferenceAnalysis | InferenceAbstention;

/** inference.json # ModelSummary */
export interface ModelSummary {
  name: string;
  version: string;
  parameters: number;
  validation_iou: number | null;
  validation_f1: number | null;
  validation_regions: string[];
  train_regions: string[];
  baseline_iou: number | null;
  /** null = not measured. Not the same as false. */
  beats_baseline: boolean | null;
  stratified_iou?: Record<string, number>;
  in_channels?: number | null;
  uses_permanent_water_prior?: boolean | null;
  training_labelling?: string | null;
  calibration_ece?: number | null;
  calibration_passes?: boolean | null;
  calibration_bar?: number | null;
  calibration_temperature?: number | null;
  calibration_report?: string | null;
  /** true once the checkpoint's sha256 matched its committed manifest. */
  checksum_verified?: boolean | null;
}

/** inference.json # ModelListResponse */
export interface ModelListResponse {
  models: ModelSummary[];
  /** null means every analysis will run the deterministic baseline. */
  default: string | null;
}

