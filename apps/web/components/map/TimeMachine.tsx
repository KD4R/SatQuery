"use client";

/**
 * The Earth Time Machine (PRD §2A) — the scrub rail under the map.
 *
 * One range input across all epochs, with tick marks and an epoch readout. The
 * map crossfades between epochs as the operator scrubs (P5-05); this component
 * owns only the rail and the state, the map owns the transition.
 *
 * Honesty rule, same as everywhere else in P5: dates come from the backend and
 * are rendered only when they exist. On a single-date dataset the rail shows
 * the states that exist — Before → After → Change — and says "dates not
 * published by the dataset" instead of inventing a Jan → Feb → Mar calendar.
 *
 * Reduced motion turns the crossfade into a cut (maplibre tween handled by the
 * map via useReducedMotion as well, so both stay in step).
 */

import { useReducedMotion } from "framer-motion";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import { formatUTC } from "../../lib/geo/format";
import type { TimeMachineModel } from "../../lib/map/timeLayers";

export function TimeMachine({
  model,
  onChange,
}: {
  model: TimeMachineModel;
  /** Fired on commit (change), not on every drag frame — the map debounces. */
  onChange?: (index: number) => void;
}) {
  const { epochs, initialIndex, hasDates } = model;
  const [index, setIndex] = useState(initialIndex);
  const reduce = useReducedMotion();
  const first = useRef(true);

  // Report the initial epoch once, so the map and the rail agree from the start.
  useEffect(() => {
    if (!first.current) return;
    first.current = false;
    onChange?.(initialIndex);
  }, [initialIndex, onChange]);

  const clamp = useCallback(
    (i: number) => Math.min(Math.max(i, 0), epochs.length - 1),
    [epochs.length],
  );

  const commit = useCallback(
    (i: number) => {
      const next = clamp(i);
      setIndex(next);
      onChange?.(next);
    },
    [clamp, onChange],
  );

  // PageUp/PageDown and Home/End work off the input too — they are part of the
  // ARIA slider pattern and free, because the input already owns arrow keys.
  const onKeyDown = useCallback(
    (e: ReactKeyboardEvent) => {
      if (e.key === "Home") {
        e.preventDefault();
        commit(0);
      } else if (e.key === "End") {
        e.preventDefault();
        commit(epochs.length - 1);
      }
    },
    [commit, epochs.length],
  );

  const epoch = epochs[index] ?? epochs[initialIndex]!;
  const tickPct = (i: number) => `${(i / (epochs.length - 1)) * 100}%`;

  return (
    <div className="tm" data-reduce={reduce ? "true" : undefined}>
      <div className="tm-head">
        <span className="tm-title label">Time machine</span>
        <span className="tm-epoch label" aria-hidden="true">
          {epoch.label}
          <span className="tm-date mono">
            {epoch.acquired
              ? formatUTC(epoch.acquired)
              : hasDates
                ? ""
                : " · date not published"}
          </span>
        </span>
        <div className="band-spacer" />
        <span className="tm-count mono" aria-hidden="true">
          {index + 1}/{epochs.length}
        </span>
      </div>

      <input
        className="tm-slider"
        type="range"
        min={0}
        max={epochs.length - 1}
        step={1}
        value={index}
        onChange={(e) => commit(Number(e.currentTarget.value))}
        onKeyDown={onKeyDown}
        aria-label="Earth time machine"
        aria-valuetext={
          epoch.acquired
            ? `${epoch.label}, ${formatUTC(epoch.acquired)}`
            : epoch.label
        }
        aria-orientation="horizontal"
        // Sizes the filled part of the webkit track (see .tm-slider in mission.css).
        style={{ "--tm-fill": `${(index / (epochs.length - 1)) * 100}%` } as CSSProperties}
      />

      <div className="tm-ticks" aria-hidden="true">
        {epochs.map((e, i) => (
          <span
            key={e.id}
            className={`tm-tick ${i === index ? "tm-tick-on" : ""}`}
            style={{ left: tickPct(i) }}
            title={e.acquired ? formatUTC(e.acquired) : e.label}
          />
        ))}
      </div>

      <div className="tm-states" role="group" aria-label="Time machine epochs">
        {epochs.map((e, i) => (
          <button
            key={e.id}
            type="button"
            className={`tm-state ${i === index ? "tm-state-on" : ""}`}
            onClick={() => commit(i)}
            aria-pressed={i === index}
          >
            {e.label}
          </button>
        ))}
      </div>

      {!hasDates ? (
        <p className="tm-note mono">
          ▲ dates not published by the dataset — the rail scrubs the states that
          exist, not a calendar
        </p>
      ) : null}
    </div>
  );
}

export default TimeMachine;
