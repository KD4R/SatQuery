"use client";

/**
 * The query box at the top of the rail (P5-03; audit F5, F9).
 *
 * Step 3 · Ask: the question and Run. Run is disabled with the reason in words
 * until the area (step 1) and dates (step 2) are valid (audit W2).
 */

import { ArrowUp, Command, LoaderCircle, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";

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
}: {
  value: string;
  onChange: (v: string) => void;
  onRun: () => void;
  running: boolean;
  onReset: () => void;
  /** Non-null blocks the run and says why, in words, next to the input. */
  blockedReason?: string | null;
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

  return (
    <section className="sqd-card sqd-query" aria-label="Mission query" id="step-ask">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">
          <Sparkles size={13} /> 3 · Ask
        </span>
        <span className={`sqd-status ${running ? "is-busy" : ""}`}>
          <i />
          {running ? "Running" : "Ready"}
        </span>
      </header>

      <div className="sqd-query-box">
        <textarea
          ref={ref}
          id="mission-query"
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
