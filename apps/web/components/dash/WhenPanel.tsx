"use client";

/**
 * Step 2 · When: the date range sent to the agent as temporal_window.
 *
 * One click for the common windows (last 7 / 30 / 90 days), or a custom range.
 * Empty means automatic: the agent searches the last 90 days and widens to a
 * year when nothing is found, and the result says which it did.
 */

import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { CalendarRange } from "lucide-react";

import {
  DATE_PRESETS,
  dateRangeProblem,
  describeRange,
  matchingPreset,
  presetRange,
} from "../../lib/live/dates";
import type { TemporalWindow } from "../../lib/api/types";

export interface WhenPanelHandle {
  focusDates: () => void;
}

export const WhenPanel = forwardRef<
  WhenPanelHandle,
  {
    demo: boolean;
    value: TemporalWindow | null;
    onChange: (w: TemporalWindow | null) => void;
    locked: boolean;
  }
>(function WhenPanel({ demo, value, onChange, locked }, ref) {
  const fromRef = useRef<HTMLInputElement | null>(null);
  const preset = matchingPreset(value);
  const [custom, setCustom] = useState(false);
  const showCustom = custom || (value !== null && preset === null);
  const today = new Date().toISOString().slice(0, 10);
  const problem = dateRangeProblem(value);

  useImperativeHandle(
    ref,
    () => ({
      focusDates: () => {
        setCustom(true);
        // after the custom fields render
        setTimeout(() => fromRef.current?.focus(), 0);
      },
    }),
    [],
  );

  const set = (key: "start" | "end", v: string) => {
    const next = { start: value?.start ?? "", end: value?.end ?? "", [key]: v };
    onChange(next.start || next.end ? next : null);
  };

  return (
    <section className="sqd-card sqd-when" aria-label="When" id="step-when">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">
          <CalendarRange size={13} /> 2 · When
        </span>
        <span className={`sqd-chip ${problem ? "is-danger" : value ? "is-ok" : ""}`}>
          {problem ? "Check dates" : value ? "Dates set" : "Automatic"}
        </span>
      </header>

      <div className="sqd-presets" role="group" aria-label="Date range">
        <button
          type="button"
          className={`sqd-preset ${value === null && !custom ? "is-on" : ""}`}
          aria-pressed={value === null && !custom}
          onClick={() => {
            setCustom(false);
            onChange(null);
          }}
          disabled={locked}
        >
          Auto
        </button>
        {DATE_PRESETS.map((p) => (
          <button
            key={p.days}
            type="button"
            className={`sqd-preset ${preset === p.days ? "is-on" : ""}`}
            aria-pressed={preset === p.days}
            onClick={() => {
              setCustom(false);
              onChange(presetRange(p.days));
            }}
            disabled={locked}
          >
            {p.label.replace("Last ", "")}
          </button>
        ))}
        <button
          type="button"
          className={`sqd-preset ${showCustom ? "is-on" : ""}`}
          aria-pressed={showCustom}
          onClick={() => setCustom(true)}
          disabled={locked}
        >
          Custom
        </button>
      </div>

      {showCustom ? (
        <div className="sqd-dates">
          <label>
            <span>From</span>
            <input
              ref={fromRef}
              type="date"
              value={value?.start ?? ""}
              max={value?.end || today}
              onChange={(e) => set("start", e.target.value)}
              aria-label="Start date"
              disabled={locked}
            />
          </label>
          <label>
            <span>To</span>
            <input
              type="date"
              value={value?.end ?? ""}
              min={value?.start || undefined}
              max={today}
              onChange={(e) => set("end", e.target.value)}
              aria-label="End date"
              disabled={locked}
            />
          </label>
        </div>
      ) : null}

      <p className={`sqd-range ${problem ? "is-danger" : ""}`} role="status">
        {problem ?? describeRange(value)}
      </p>
      {demo ? (
        <p className="sqd-note">Demo mode replays a pinned scene, so dates are not applied; live runs send them.</p>
      ) : null}
    </section>
  );
});
