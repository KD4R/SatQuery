"use client";
import {
  ArrowUp,
  Command,
  LoaderCircle,
  Paperclip,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
const templates = [
  "Flood impact",
  "Vegetation loss",
  "Urban expansion",
  "Cloud → SAR",
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
  const [expanded, setExpanded] = useState(false);
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
    <section className="card copilot-card">
      <div className="card-head">
        <div>
          <div className="title-row">
            <Sparkles size={14} />
            <div className="card-title">MISSION COPILOT</div>
          </div>
          <div className="card-sub">
            Natural language → mission plan → evidence
          </div>
        </div>
        <span className={`status-chip ${running ? "busy" : ""}`}>
          <i />
          {running ? "Running" : "Ready"}
        </span>
      </div>
      <div className={`query-box ${expanded ? "focus" : ""}`}>
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setExpanded(true)}
          onBlur={() => setExpanded(false)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (!running && !blockedReason) onRun();
            }
          }}
          aria-label="Mission query"
        />
        <div className="query-footer">
          <span className="hint">
            <Command size={10} /> CTRL K · ENTER TO RUN · SHIFT ENTER
          </span>
          <div className="query-actions">
            <button className="small-icon" title="Attach context" aria-label="Attach context" disabled>
              <Paperclip size={14} />
            </button>
            <button className="small-icon" title="Reset" aria-label="Reset mission" onClick={onReset}>
              <RotateCcw size={14} />
            </button>
            <button
              className="send"
              onClick={onRun}
              disabled={running || Boolean(blockedReason)}
              aria-label="Run analysis"
              title={blockedReason ?? "Run analysis"}
            >
              {running ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <ArrowUp size={16} />
              )}
            </button>
          </div>
        </div>
      </div>
      {blockedReason ? (
        <p className="hint" role="alert" style={{ margin: "6px 2px 0" }}>
          {blockedReason}
        </p>
      ) : null}
      <div className="template-row">
        {templates.map((t) => (
          <button
            key={t}
            className="template"
            onClick={() =>
              onChange(
                t === "Flood impact"
                  ? "Show flood-affected areas in the selected AOI and explain why you chose SAR."
                  : `Analyze ${t.toLowerCase()} for the selected AOI and show the evidence.`,
              )
            }
          >
            {t}
          </button>
        ))}
      </div>
    </section>
  );
}
