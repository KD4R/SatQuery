/**
 * The "When" step: date presets, validation and the window the agent receives.
 *
 * Dates are whole days in the UI ("YYYY-MM-DD"); the agent's temporal_window
 * takes instants, so the range is sent as start-of-day to end-of-day UTC.
 */

import type { TemporalWindow } from "../api/types";

export type DatePreset = 7 | 30 | 90;

export const DATE_PRESETS: readonly { days: DatePreset; label: string }[] = [
  { days: 7, label: "Last 7 days" },
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
];

function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** The last `days` days, ending today (UTC). */
export function presetRange(days: number, today: Date = new Date()): TemporalWindow {
  const end = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  const start = new Date(end.getTime() - days * 86_400_000);
  return { start: isoDay(start), end: isoDay(end) };
}

/** Which preset (if any) a range equals, for highlighting the chip. */
export function matchingPreset(w: TemporalWindow | null, today: Date = new Date()): DatePreset | null {
  if (!w) return null;
  for (const p of DATE_PRESETS) {
    const r = presetRange(p.days, today);
    if (r.start === w.start && r.end === w.end) return p.days;
  }
  return null;
}

/** A reason the range cannot be used, or null when it can (or is empty). */
export function dateRangeProblem(w: TemporalWindow | null, today: Date = new Date()): string | null {
  if (!w) return null;
  if (!w.start || !w.end) return "Set both dates, or clear them to let the agent choose.";
  if (w.start > w.end) return "The start date must be before the end date.";
  if (w.end > isoDay(today)) return "The end date cannot be in the future.";
  return null;
}

/** Day count of a valid range, inclusive of both ends. */
export function rangeDays(w: TemporalWindow): number {
  return Math.round((Date.parse(w.end) - Date.parse(w.start)) / 86_400_000) + 1;
}

/** "1 Jul 2024 → 15 Jul 2024 · 15 days" */
export function describeRange(w: TemporalWindow | null): string {
  if (!w || dateRangeProblem(w)) return "Automatic: the last 90 days, widened to a year if nothing is found";
  const fmt = (s: string) =>
    new Date(`${s}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  return `${fmt(w.start)} → ${fmt(w.end)} · ${rangeDays(w)} days`;
}

/** What the agent receives: instants covering the whole days, or null for automatic. */
export function toTemporalWindow(w: TemporalWindow | null): TemporalWindow | null {
  if (!w || dateRangeProblem(w)) return null;
  return { start: `${w.start}T00:00:00Z`, end: `${w.end}T23:59:59Z` };
}
