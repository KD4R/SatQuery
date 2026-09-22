/**
 * View models for the mission intelligence panel (P5-07 … P5-14).
 *
 * WHY THESE ARE NOT IN lib/api/types.ts
 * -------------------------------------
 * lib/api/types.ts holds DTOs transcribed from a published OpenAPI schema. These are
 * not that. The gateway currently exposes eleven routes -- missions, runs, agent,
 * jobs, health -- and *none* for observations, tiles, change geometry, evidence,
 * reports or monitoring. P5-07 through P5-14 are specified against endpoints that do
 * not exist yet.
 *
 * So these are P5's own view models: the shape the UI needs, declared in one place,
 * fed today by lib/fixtures/ and tomorrow by an adapter over whatever P2 and P4 ship.
 * When those routes land, only lib/api/ changes -- the components are already written
 * against this.
 *
 * Every field that the backend might not supply is explicitly nullable, because the
 * panels render NOT AVAILABLE for null rather than hiding the row. A missing value
 * has to stay visible; that is the whole point of the WHY panel.
 */

import type { GeoJSONPolygon } from "../api/types";

/* ── Observations (P5-07) ─────────────────────────────────────────────────── */

export type Sensor = "SENTINEL-1" | "SENTINEL-2" | string;

export interface Observation {
  id: string;
  sensor: Sensor;
  /** ISO-8601, or null when the source does not publish an acquisition time. */
  acquired: string | null;
  /** Why `acquired` is null, shown to the operator. */
  acquiredUnavailableReason?: string;
  /** Dataset or collection this came from, for provenance. */
  dataset: string;
  /** Ground sample distance in metres, or null if unknown. */
  resolutionM: number | null;
  /** 0..1, or null for SAR where the notion does not apply. */
  cloudFraction: number | null;
  /** [west, south, east, north] in EPSG:4326. */
  bbox: [number, number, number, number];
  /** Rendered raster for the comparison viewer. */
  imageUrl: string | null;
  /** What the image actually shows, verbatim, for the caption. */
  imageDescription: string;
}

/**
 * The left and right halves of the before/after viewer.
 *
 * `before` is nullable on purpose: single-date datasets have no pre-event scene, and
 * the viewer has a first-class state for that rather than faking a pair.
 */
export interface ComparisonPair {
  before: Observation | null;
  beforeUnavailableReason?: string;
  after: Observation;
}

/* ── Change and confidence (P5-08, P5-11) ─────────────────────────────────── */

export interface ChangeSummary {
  /** What changed, in the analyst's words. */
  headline: string;
  /** Total area of the change polygons, km². */
  areaSqKm: number;
  polygonCount: number;
  /** Fraction of the AOI the sensor could actually see. */
  coverageFraction: number;
  /** Fraction of the analysed area that is newly water. */
  changeFraction: number;
  /** Water already present before the event, as a fraction of analysed area. */
  baselineFraction: number;
}

export interface Confidence {
  /** 0..1. */
  score: number;
  /** Did it clear the gate the agent applies. */
  passedGate: boolean;
  /** Named reasons the score is not higher. Never empty when score < 1. */
  uncertaintyFactors: string[];
  /** Fraction of the analysed area the model declined to call either way. */
  uncertainFraction: number | null;
  /** What the system will do about it: proceed, escalate, abstain. */
  action: string;
}

/* ── Evidence (P5-09) ─────────────────────────────────────────────────────── */

export type EvidenceKind =
  | "observation"
  | "comparison"
  | "geometry"
  | "sensor"
  | "confidence"
  | "temporal"
  | "model";

/**
 * One link in the WHY chain. `value` null renders NOT AVAILABLE with `reason`,
 * which is how the panel stays trustworthy when the backend is incomplete.
 */
export interface EvidenceNode {
  id: string;
  kind: EvidenceKind;
  label: string;
  value: string | null;
  reason?: string;
  /** Where this came from — service, dataset, model version. */
  provenance: string | null;
}

/* ── Sensor arbitration (P5-10) ───────────────────────────────────────────── */

export interface SensorReading {
  sensor: Sensor;
  /** What this sensor concluded, e.g. "Flood signal" or "Cloud-obscured". */
  finding: string;
  confidence: number | null;
  /** Why this sensor is or is not usable here. */
  note: string;
}

export interface SensorArbitration {
  readings: SensorReading[];
  /** Which sensor the agent chose. */
  primary: Sensor | null;
  secondary: Sensor | null;
  rationale: string | null;
  /** True when the readings materially conflict and an operator should look. */
  disagreement: boolean;
  arbitrationScore: number | null;
}

/* ── Mission memory and monitoring (P5-12, P5-13) ─────────────────────────── */

export interface MissionEvent {
  id: string;
  at: string;
  kind: "run" | "observation" | "detection" | "monitoring" | "report";
  summary: string;
  detail: string | null;
}

export interface MonitoringStatus {
  active: boolean;
  aoiName: string;
  intervalHours: number | null;
  lastObservation: string | null;
  nextObservation: string | null;
  changeStatus: string;
  recentEvents: MissionEvent[];
}

/* ── The whole console state ──────────────────────────────────────────────── */

export interface ConsoleScenario {
  missionId: string;
  runId: string;
  traceId: string;
  query: string;
  aoiName: string;
  aoi: GeoJSONPolygon;
  aoiAreaSqKm: number;
  comparison: ComparisonPair;
  change: ChangeSummary;
  confidence: Confidence;
  evidence: EvidenceNode[];
  arbitration: SensorArbitration;
  monitoring: MonitoringStatus;
  history: MissionEvent[];
  /** Raster overlays keyed by layer id, for the map. */
  overlays: Record<string, { url: string; bbox: [number, number, number, number] }>;
  changeGeoJsonUrl: string;
  modelVersion: string | null;
  processingVersion: string | null;
}

/* ── Run timeline (P5-04) ─────────────────────────────────────────────────── */

/**
 * Lifecycle of one stage in a run.
 *
 * Lives here rather than beside the demo script because the *live* timeline is
 * built from these too. A type the production path depends on must not be
 * reachable only through lib/fixtures/ — see lib/fixtures/isolation.test.ts.
 *
 * `degraded` is deliberately distinct from both `completed` and `failed`: a stage
 * that finished having analysed less than half the AOI is neither.
 */
export type StageState =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "degraded";
