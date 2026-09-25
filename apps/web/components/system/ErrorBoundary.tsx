"use client";

/**
 * Error boundaries and failure states (P5-16, and the PRD's Failure Modes table).
 *
 * The rule these enforce: a failed operation looks failed. It carries the run id
 * and trace id an operator needs to hand to someone, names what could not be done,
 * and offers a retry only when retrying could plausibly help. A component that
 * throws takes down its panel, not the console.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

import { Label, StatusChip } from "./primitives";
import type { ErrorResponse } from "../../lib/api/types";

/* ── Failure state ────────────────────────────────────────────────────────── */

export function ErrorState({
  title,
  error,
  runId,
  onRetry,
}: {
  title: string;
  error: ErrorResponse | Error;
  runId?: string | null;
  onRetry?: () => void;
}) {
  const envelope: ErrorResponse =
    error instanceof Error
      ? { code: error.name, message: error.message, details: [], trace_id: null }
      : error;

  return (
    <div
      role="alert"
      style={{
        padding: 14,
        border: "1px solid var(--hairline-signal)",
        borderLeft: "2px solid var(--signal)",
        background: "var(--surface-1)",
      }}
    >
      <div className="row" style={{ marginBottom: 8 }}>
        <Label as="h3">
          <span className="sig">{title}</span>
        </Label>
        <div className="band-spacer" />
        <StatusChip tone="warn">{envelope.code}</StatusChip>
      </div>

      <p style={{ margin: "0 0 10px", fontSize: 12, lineHeight: 1.55, color: "var(--ink-dim)" }}>
        {envelope.message}
      </p>

      <div style={{ borderTop: "1px solid var(--hairline)", paddingTop: 8 }}>
        <IdRow k="Run id" v={runId ?? null} />
        <IdRow k="Trace id" v={envelope.trace_id ?? null} />
      </div>

      {Array.isArray(envelope.details) && envelope.details.length > 0 ? (
        <details style={{ marginTop: 8 }}>
          <summary className="label" style={{ cursor: "pointer" }}>
            Details
          </summary>
          <pre
            className="mono faint"
            style={{
              margin: "6px 0 0",
              fontSize: 9.5,
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              maxHeight: 160,
              overflow: "auto",
            }}
          >
            {JSON.stringify(envelope.details, null, 1)}
          </pre>
        </details>
      ) : null}

      {onRetry ? (
        <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}

function IdRow({ k, v }: { k: string; v: string | null }) {
  return (
    <div className="readout" style={{ minHeight: 18 }}>
      <Label faint>{k}</Label>
      {v ? (
        <span className="readout-value" style={{ fontSize: 10 }}>
          {v}
        </span>
      ) : (
        <span className="readout-value readout-value-na" style={{ fontSize: 10 }}>
          NOT AVAILABLE
        </span>
      )}
    </div>
  );
}

/* ── Empty and loading ────────────────────────────────────────────────────── */

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div style={{ padding: 24, textAlign: "center" }}>
      <p className="label label-faint" style={{ lineHeight: 1.9 }}>
        {title}
        {hint ? (
          <>
            <br />
            {hint}
          </>
        ) : null}
      </p>
    </div>
  );
}

export function LoadingState({ label }: { label: string }) {
  // No spinner. A pulsing caret says "waiting" without implying a known duration,
  // which a progress bar would (P5-04: never show progress that was not reported).
  return (
    <div
      role="status"
      aria-live="polite"
      style={{ padding: 20, display: "flex", gap: 8, justifyContent: "center" }}
    >
      <span className="label">{label}</span>
      <span className="label sig blink" aria-hidden="true">
        ▌
      </span>
    </div>
  );
}

/* ── Boundary ─────────────────────────────────────────────────────────────── */

interface BoundaryProps {
  children: ReactNode;
  /** Named so the operator knows which part of the console failed. */
  area: string;
}

interface BoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Deliberately not sent anywhere yet: there is no frontend telemetry sink in
    // the gateway contract. When P6 adds one, this is the single place to wire it.
    console.error(`[${this.props.area}]`, error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <ErrorState
          title={`${this.props.area} failed to render`}
          error={this.state.error}
          onRetry={() => this.setState({ error: null })}
        />
      );
    }
    return this.props.children;
  }
}
