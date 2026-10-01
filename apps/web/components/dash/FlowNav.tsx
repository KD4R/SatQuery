"use client";

/**
 * The mission flow navigation (replaces the floating guide).
 *
 * Where → When → Ask → Run → Result, pinned at the top of the rail. Each step
 * shows its state (done, current, waiting, failed) and is a button that takes
 * the operator to the control for that step: the place search, the dates, the
 * question, Run itself, or the result. "Current" is the first step still
 * needing something, so the bar always points at what to do next.
 */

import { Check, Loader2, X } from "lucide-react";

export type FlowState = "done" | "current" | "todo" | "running" | "error" | "optional";

export interface FlowStep {
  key: string;
  label: string;
  hint: string;
  state: FlowState;
  onGo: () => void;
  disabled?: boolean;
}

export function FlowNav({ steps }: { steps: FlowStep[] }) {
  return (
    <nav className="sqd-flow" aria-label="Mission steps">
      <ol>
        {steps.map((s, i) => (
          <li key={s.key} className={`is-${s.state}`}>
            <button
              type="button"
              onClick={s.onGo}
              disabled={s.disabled}
              aria-current={s.state === "current" || s.state === "running" ? "step" : undefined}
              title={s.hint}
            >
              <span className="sqd-flow-dot" aria-hidden="true">
                {s.state === "done" ? (
                  <Check size={12} />
                ) : s.state === "running" ? (
                  <Loader2 size={12} className="spin" />
                ) : s.state === "error" ? (
                  <X size={12} />
                ) : (
                  i + 1
                )}
              </span>
              <span className="sqd-flow-text">
                <b>{s.label}</b>
                <small>{s.hint}</small>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}
