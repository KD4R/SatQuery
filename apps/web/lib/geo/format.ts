/**
 * Coordinate and measurement formatting for the telemetry readouts (P5-05).
 *
 * All of these are pure and deterministic: the demo has to render identically on
 * every run, and these functions sit under numbers that appear on screen.
 */

/** Signed decimal degrees, fixed to 4dp (~11 m). Matches the map readout. */
export function formatLat(lat: number): string {
  return `${lat >= 0 ? "" : "-"}${Math.abs(lat).toFixed(4)}`;
}

export function formatLon(lon: number): string {
  return `${lon >= 0 ? "" : "-"}${Math.abs(lon).toFixed(4)}`;
}

export function formatZoom(zoom: number): string {
  return zoom.toFixed(1);
}

/** Hectares below 100 km², square kilometres above. */
export function formatArea(sqMetres: number | null): string {
  if (sqMetres === null || !Number.isFinite(sqMetres)) return "NOT AVAILABLE";
  const sqKm = sqMetres / 1_000_000;
  if (sqKm < 100) {
    return `${(sqMetres / 10_000).toLocaleString("en-GB", {
      maximumFractionDigits: 1,
    })} ha`;
  }
  return `${sqKm.toLocaleString("en-GB", { maximumFractionDigits: 1 })} km²`;
}

/** Grouped-digit counter, e.g. 021.937.832 — the reference film's numeral style. */
export function groupDigits(value: number, groups = 3): string {
  const digits = Math.max(0, Math.trunc(value)).toString();
  const padded = digits.padStart(groups * 3, "0");
  return (padded.match(/.{1,3}/g) ?? [padded]).join(".");
}

/** `2026-09-14 05:42 UTC` — the acquisition-timestamp format used throughout. */
export function formatUTC(iso: string | null | undefined): string {
  if (!iso) return "NOT AVAILABLE";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "NOT AVAILABLE";
  const p = (n: number) => n.toString().padStart(2, "0");
  return (
    `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ` +
    `${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`
  );
}

/** Percentage with no decimal place, for confidence and coverage readouts. */
export function formatPercent(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) {
    return "NOT AVAILABLE";
  }
  return `${Math.round(fraction * 100)}%`;
}

/**
 * Confidence band. Deliberately coarse: the PRD requires uncertainty to be
 * explained rather than presented as a single authoritative number.
 */
export function confidenceBand(score: number): "HIGH" | "MODERATE" | "LOW" {
  if (score >= 0.8) return "HIGH";
  if (score >= 0.6) return "MODERATE";
  return "LOW";
}
