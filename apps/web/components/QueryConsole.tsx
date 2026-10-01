"use client";

/**
 * The query box at the top of the rail (P5-03; audit F5, F9).
 *
 * The question, an optional date range, and Run. Run is disabled with the reason
 * in words until the inputs are valid (audit W2). The date range maps to the
 * agent's temporal_window; left empty, the agent searches the last 90 days and
 * widens to a year when nothing is found, and says so in the result.
 */

import { ArrowUp, CalendarRange, Command, LoaderCircle, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";

import type { TemporalWindow } from "../lib/api/types";

/** Prompts for what the live pipeline can actually answer: surface water. */
const TEMPLATES: { label: string; text: string }[] = [
  { label: "Flood extent", text: "Map the flood extent in the selected area and explain why you chose SAR." },
  { label: "Water now", text: "How much surface water is in the selected area on the latest pass?" },
  { label: "Event window", text: "Show flooding in the selected area during the chosen dates." },
];

export default function QueryConsole({
  value,
  onChange,
  onRun,
  running,
  onReset,
  blockedReason = null,
  window: dates = null,
  onWindowChange,
  showDates = false,
}: {
  value: string;
  onChange: (v: string) => void;
  onRun: () => void;
  running: boolean;
  onReset: () => void;
  /** Non-null blocks the run and says why, in words, next to the input. */
  blockedReason?: string | null;
  window?: TemporalWindow | null;
  onWindowChange?: (w: TemporalWindow | null) => void;
  showDates?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        ref.current?.focus();
      }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, []);

  const today = new Date().toISOString().slice(0, 10);
  const setDate = (key: "start" | "end", v: string) => {
    if (!onWindowChange) return;
    const next = { start: dates?.start ?? "", end: dates?.end ?? "", [key]: v };
    onWindowChange(next.start || next.end ? next : null);
  };

  return (
    <section className="sqd-card sqd-query" aria-label="Mission query">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">
          <Sparkles size={13} /> Ask
        </span>
        <span className={`sqd-status ${running ? "is-busy" : ""}`}>
          <i />
          {running ? "Running" : "Ready"}
        </span>
      </header>

      <div className="sqd-query-box">
        <textarea
          ref={ref}
          value={value}
          rows={3}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!running && !blockedReason) onRun();
            }
          }}
          aria-label="Mission query"
          placeholder="Ask about surface water or flooding in the area you draw"
        />
        <div className="sqd-query-foot">
          <span className="sqd-hint">
            <Command size={10} />K focus · Enter run
          </span>
          <div className="sqd-query-actions">
            <button className="sqd-icon-btn" title="Reset" aria-label="Reset mission" onClick={onReset} type="button">
              <RotateCcw size={14} />
            </button>
            <button
              className="sqd-send"
              onClick={onRun}
              disabled={running || Boolean(blockedReason)}
              aria-label="Run analysis"
              title={blockedReason ?? "Run analysis"}
              type="button"
            >
              {running ? <LoaderCircle className="spin" size={16} /> : <ArrowUp size={16} />}
            </button>
          </div>
        </div>
      </div>

      {showDates ? (
        <fieldset className="sqd-dates" disabled={running}>
          <legend>
            <CalendarRange size={12} /> Dates <small>(optional)</small>
          </legend>
          <label>
            <span>From</span>
            <input
              type="date"
              value={dates?.start ?? ""}
              max={dates?.end || today}
              onChange={(e) => setDate("start", e.target.value)}
              aria-label="Start date"
            />
          </label>
          <label>
            <span>To</span>
            <input
              type="date"
              value={dates?.end ?? ""}
              min={dates?.start || undefined}
              max={today}
              onChange={(e) => setDate("end", e.target.value)}
              aria-label="End date"
            />
          </label>
          {dates ? (
            <button type="button" className="sqd-link" onClick={() => onWindowChange?.(null)}>
              Clear
            </button>
          ) : null}
        </fieldset>
      ) : null}

      {blockedReason ? (
        <p className="sqd-blocked" role="status">
          {blockedReason}
        </p>
      ) : null}

      <div className="sqd-templates">
        {TEMPLATES.map((t) => (
          <button key={t.label} className="sqd-template" type="button" onClick={() => onChange(t.text)}>
            {t.label}
          </button>
        ))}
      </div>
    </section>
  );
}

/** Validate a partially filled range. Returns a reason, or null when usable. */
export function dateRangeProblem(w: TemporalWindow | null): string | null {
  if (!w) return null;
  if (!w.start || !w.end) return "Set both dates, or clear them to let the agent choose.";
  if (w.start > w.end) return "The start date must be before the end date.";
  if (w.end > new Date().toISOString().slice(0, 10)) return "The end date cannot be in the future.";
  return null;
}
