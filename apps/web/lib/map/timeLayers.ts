/**
 * The Earth Time Machine's model (PRD §2A).
 *
 * The PRD asks for a timeline that scrubs the map between historical states.
 * The honest version of that is built from the temporal states a run actually
 * has: the before scene, the after scene, and the semantic change map between
 * them. Dates appear only when the backend supplies one — a Jan → Feb → Mar
 * rail pasted over a single-date dataset would contradict the WHY panel three
 * inches away, which renders NOT AVAILABLE for exactly that missing timestamp.
 *
 * When P4's TiTiler epochs land, each dated acquisition becomes one more
 * TimeEpoch in this list; nothing in the component or the map changes, because
 * both already treat "epoch" as opaque data. Until then this module is where
 * the demo's three states live.
 *
 * Pure module: no React, no maplibre. Testable and reusable by the report page.
 */

import type { ConsoleScenario } from "../model/console";

/** One scrubbable temporal state of the map. */
export interface TimeEpoch {
  /** Stable layer key — also the maplibre source/layer suffix. */
  id: string;
  /** Short name on the scrubber, e.g. "Before". */
  label: string;
  /** Raster image for this state. */
  url: string;
  /** [west, south, east, north] in EPSG:4326. */
  bbox: [number, number, number, number];
  /** Paint opacity when this epoch is the active one (change maps read better dimmer). */
  opacity: number;
  /** ISO-8601 acquisition time, or null — never invented (P5-17 determinism). */
  acquired: string | null;
  /** Why `acquired` is null, shown to the operator. */
  unavailableReason?: string;
}

export interface TimeMachineModel {
  /** Ordered oldest → newest → derived. Never fewer than two. */
  epochs: TimeEpoch[];
  /** The epoch a completed run should open on: the latest scene, not the first. */
  initialIndex: number;
  /**
   * True only when every *scene* epoch carries a real acquisition date. The
   * change map is derived and never dated. When false the scrubber says so
   * once, rather than dressing a state rail up as a calendar.
   */
  hasDates: boolean;
}

/**
 * Builds the machine from a scenario's overlay stack:
 *   Before (permanent-water baseline) → After (observed) → Change (semantic map).
 *
 * Returns null when the scenario carries fewer than two temporal states — a
 * scrubber over a single image is theatre, and the component is not rendered.
 */
export function buildTimeMachine(scenario: ConsoleScenario): TimeMachineModel | null {
  const s = scenario.overlays;
  const epochs: TimeEpoch[] = [];

  const baseline = s["baseline"];
  if (baseline) {
    epochs.push({
      id: "tm-baseline",
      label: "Before",
      url: baseline.url,
      bbox: baseline.bbox,
      opacity: 1,
      acquired: scenario.comparison.before?.acquired ?? null,
      unavailableReason:
        scenario.comparison.before?.acquiredUnavailableReason ??
        scenario.comparison.beforeUnavailableReason ??
        "No dated pre-event scene exists for this AOI.",
    });
  }

  const observed = s["observed"];
  if (observed) {
    epochs.push({
      id: "tm-observed",
      label: "After",
      url: observed.url,
      bbox: observed.bbox,
      opacity: 1,
      acquired: scenario.comparison.after.acquired,
      unavailableReason: scenario.comparison.after.acquiredUnavailableReason,
    });
  }

  // Whether the scene rail is a dated timeline can only be decided before the
  // derived change map joins it — it never carries a date of its own.
  const hasDates =
    epochs.length > 0 && epochs.every((e) => e.acquired !== null);

  const change = s["change"];
  if (change) {
    epochs.push({
      id: "tm-change",
      label: "Change",
      url: change.url,
      bbox: change.bbox,
      // The change raster is a highlight over dark water, not a full scene; at
      // full opacity it drowns the canvas it sits on.
      opacity: 0.92,
      acquired: null,
      unavailableReason:
        "A difference map computed from the scenes, not an acquisition — it has " +
        "no date of its own. Dates belong to the epochs it was derived from.",
    });
  }

  if (epochs.length < 2) return null;

  // A completed run opens on the observed scene — the latest thing the sensor
  // actually saw — with the derived change map one scrub to the right.
  const observedIndex = epochs.findIndex((e) => e.id === "tm-observed");

  return {
    epochs,
    initialIndex: observedIndex >= 0 ? observedIndex : epochs.length - 1,
    hasDates,
  };
}

/**
 * Target raster-opacity per epoch layer for the scrubber at `index`.
 *
 * The active epoch gets its own paint opacity; every other epoch gets 0 so the
 * map crossfades between neighbouring scenes as the operator scrubs. MapLibre
 * does not tween paint properties itself, so the map component walks layer
 * opacity toward these targets — instantly when the operator prefers reduced
 * motion.
 */
export function epochOpacities(
  model: TimeMachineModel,
  index: number,
): Record<string, number> {
  const clamped = Math.min(Math.max(index, 0), model.epochs.length - 1);
  const out: Record<string, number> = {};
  for (const [i, e] of model.epochs.entries()) {
    out[e.id] = i === clamped ? e.opacity : 0;
  }
  return out;
}
