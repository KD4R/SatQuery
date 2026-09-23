/**
 * AOI validation (P5-06).
 *
 * Validation runs in the browser before anything is sent, so the operator sees what
 * is wrong with the polygon while they are still drawing it. The backend validates
 * again -- this is a usability layer, never a security boundary. Every rule returns
 * an actionable message, because the PRD requires invalid AOI states to be shown,
 * not hidden.
 */

import area from "@turf/area";
import kinks from "@turf/kinks";
import { polygon as turfPolygon } from "@turf/helpers";

import type { GeoJSONPolygon } from "../api/types";

export type Severity = "error" | "warning";

export interface Finding {
  /** Stable key so tests and the UI can refer to a rule without matching prose. */
  rule: string;
  severity: Severity;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  findings: Finding[];
  /** Square metres, or null when the geometry is too broken to measure. */
  areaSqM: number | null;
}

/**
 * Upper bound on AOI size. Chosen so a single analysis stays inside the PRD's
 * "<10s small analysis" budget; above it the operator is asked to split the area
 * rather than being allowed to queue work that will time out.
 */
export const MAX_AREA_SQ_KM = 50_000;

/** Below this an AOI is smaller than a few Sentinel-1 pixels and cannot be analysed. */
export const MIN_AREA_SQ_KM = 0.5;

function ringIsClosed(ring: number[][]): boolean {
  if (ring.length < 4) return false;
  const first = ring[0];
  const last = ring[ring.length - 1];
  return first !== undefined && last !== undefined
    && first[0] === last[0] && first[1] === last[1];
}

/**
 * Return the rings with each one explicitly closed. Turf requires closure; the
 * operator mid-draw has not provided it yet.
 */
function closeRings(rings: number[][][]): number[][][] {
  return rings.map((ring) => (ringIsClosed(ring) ? ring : [...ring, ring[0] as number[]]));
}

function coordinatesInRange(ring: number[][]): boolean {
  return ring.every((position) => {
    const [lon, lat] = position;
    return (
      typeof lon === "number" &&
      typeof lat === "number" &&
      Number.isFinite(lon) &&
      Number.isFinite(lat) &&
      lon >= -180 &&
      lon <= 180 &&
      lat >= -90 &&
      lat <= 90
    );
  });
}

export function validateAOI(geometry: GeoJSONPolygon | null): ValidationResult {
  const findings: Finding[] = [];

  if (!geometry) {
    return {
      valid: false,
      areaSqM: null,
      findings: [
        { rule: "aoi.missing", severity: "error", message: "No AOI has been drawn." },
      ],
    };
  }

  if (geometry.type !== "Polygon") {
    return {
      valid: false,
      areaSqM: null,
      findings: [
        {
          rule: "aoi.type",
          severity: "error",
          message: `Geometry must be a Polygon; received ${String(geometry.type)}.`,
        },
      ],
    };
  }

  const exterior = geometry.coordinates?.[0];

  if (!exterior || exterior.length < 4) {
    return {
      valid: false,
      areaSqM: null,
      findings: [
        {
          rule: "aoi.vertices",
          severity: "error",
          message: "An AOI needs at least three distinct corners.",
        },
      ],
    };
  }

  if (!coordinatesInRange(exterior)) {
    return {
      valid: false,
      areaSqM: null,
      findings: [
        {
          rule: "aoi.bounds",
          severity: "error",
          message: "A coordinate falls outside longitude -180..180 / latitude -90..90.",
        },
      ],
    };
  }

  if (!ringIsClosed(exterior)) {
    // Recoverable: the draw tool closes the ring on completion. Flagged, not fatal,
    // so a polygon mid-draw does not read as broken.
    findings.push({
      rule: "aoi.unclosed",
      severity: "warning",
      message: "The outline is not closed yet.",
    });
  }

  let areaSqM: number | null = null;
  try {
    // Measure the ring the draw tool will produce, not the half-drawn one: turf
    // rejects an unclosed ring outright, which would turn the "still drawing"
    // warning above into a hard error and contradict it.
    const feature = turfPolygon(closeRings(geometry.coordinates));

    if (kinks(feature).features.length > 0) {
      findings.push({
        rule: "aoi.selfIntersects",
        severity: "error",
        message: "The outline crosses itself. Move the crossing corner.",
      });
    }

    areaSqM = area(feature);

    const areaSqKm = areaSqM / 1_000_000;
    if (areaSqKm > MAX_AREA_SQ_KM) {
      findings.push({
        rule: "aoi.tooLarge",
        severity: "error",
        message:
          `AOI is ${Math.round(areaSqKm).toLocaleString()} km², above the ` +
          `${MAX_AREA_SQ_KM.toLocaleString()} km² limit. Split it into smaller areas.`,
      });
    } else if (areaSqKm < MIN_AREA_SQ_KM) {
      findings.push({
        rule: "aoi.tooSmall",
        severity: "error",
        message:
          `AOI is ${areaSqKm.toFixed(2)} km², below the ${MIN_AREA_SQ_KM} km² ` +
          `minimum — smaller than the sensor can resolve.`,
      });
    }
  } catch {
    findings.push({
      rule: "aoi.unmeasurable",
      severity: "error",
      message: "The outline could not be measured. Redraw it.",
    });
  }

  // Crossing the antimeridian breaks area and bbox maths in most of the stack.
  const lons = exterior.map((p) => p[0] as number);
  if (Math.max(...lons) - Math.min(...lons) > 180) {
    findings.push({
      rule: "aoi.antimeridian",
      severity: "error",
      message: "AOI appears to cross the antimeridian, which is not supported.",
    });
  }

  return {
    valid: !findings.some((f) => f.severity === "error"),
    findings,
    areaSqM,
  };
}
