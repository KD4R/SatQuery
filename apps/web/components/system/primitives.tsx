"use client";

/**
 * The small vocabulary every panel is built from (P5-01).
 *
 * These exist so that a label, a readout row or a state chip is written once and
 * looks the same in the evidence panel, the monitoring screen and the report. Each
 * maps to a class in app/mission.css.
 */

import type { ReactNode } from "react";

/* ── Label ────────────────────────────────────────────────────────────────── */

export function Label({
  children,
  faint = false,
  as: Tag = "span",
}: {
  children: ReactNode;
  faint?: boolean;
  as?: "span" | "div" | "h2" | "h3";
}) {
  return <Tag className={`label${faint ? " label-faint" : ""}`}>{children}</Tag>;
}

/* ── NotAvailable ─────────────────────────────────────────────────────────── */

/**
 * Rendered wherever the backend has not supplied a value.
 *
 * This is a component rather than a string because it is the load-bearing piece of
 * the WHY panel's credibility: an operator has to be able to tell "we measured this
 * and it is zero" from "we do not know". `reason` is surfaced on hover and to
 * screen readers so the gap is explained, not merely marked.
 */
export function NotAvailable({ reason }: { reason?: string }) {
  return (
    <span
      className="readout-value readout-value-na"
      title={reason ?? "Not supplied by the backend."}
    >
      NOT AVAILABLE
      {reason ? <span className="sr-only"> — {reason}</span> : null}
    </span>
  );
}

/* ── Readout ──────────────────────────────────────────────────────────────── */

/**
 * One label/value row. Passing `value={null}` renders NOT AVAILABLE rather than an
 * empty cell, so a missing field never looks like a measured blank.
 */
export function Readout({
  label,
  value,
  reason,
  tone,
}: {
  label: string;
  value: ReactNode | null | undefined;
  reason?: string;
  tone?: "signal" | "amber" | "dim";
}) {
  const toneClass =
    tone === "signal" ? " sig" : tone === "amber" ? " amb" : tone === "dim" ? " dim" : "";
  return (
    <div className="readout">
      <Label faint>{label}</Label>
      {value === null || value === undefined || value === "" ? (
        <NotAvailable reason={reason} />
      ) : (
        <span className={`readout-value${toneClass}`}>{value}</span>
      )}
    </div>
  );
}

/* ── StatusChip ───────────────────────────────────────────────────────────── */

export type ChipTone = "active" | "warn" | "ok" | "idle" | "fixture";

/**
 * State is carried by a glyph as well as a colour, so the chip still reads for a
 * colour-blind operator and in a grayscale projector (P5-15: colour is never the
 * only indication of state).
 */
const GLYPH: Record<ChipTone, string> = {
  active: "●",
  warn: "▲",
  ok: "✓",
  idle: "○",
  fixture: "◆",
};

export function StatusChip({
  tone = "idle",
  children,
  title,
}: {
  tone?: ChipTone;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span className={`chip chip-${tone}`} data-glyph={GLYPH[tone]} title={title}>
      {children}
    </span>
  );
}

/* ── ProvenanceBadge ──────────────────────────────────────────────────────── */

/**
 * Renders on every surface fed by a fixture (P5-17).
 *
 * Deliberately loud. The brief states twice that demo data must not be passed off
 * as backend data; a badge the operator has to hunt for fails that just as surely
 * as no badge at all.
 */
export function ProvenanceBadge({
  source,
  at,
}: {
  source: "gateway" | "fixture";
  at?: string;
}) {
  if (source === "gateway") return null;
  return (
    <StatusChip
      tone="fixture"
      title={`Deterministic demo fixture${at ? `, pinned at ${at}` : ""}. Not a backend response.`}
    >
      Demo fixture
    </StatusChip>
  );
}

/* ── Panel scaffolding ────────────────────────────────────────────────────── */

export function Panel({
  title,
  actions,
  children,
  labelledBy,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
  labelledBy?: string;
}) {
  const id = labelledBy ?? `panel-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section className="panel" aria-labelledby={id}>
      <header className="panel-head">
        <Label as="h2">
          <span id={id}>{title}</span>
        </Label>
        <div className="band-spacer" />
        {actions}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export function PanelSection({
  title,
  children,
  actions,
}: {
  title?: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="panel-section">
      {title ? (
        <div className="row" style={{ marginBottom: 6 }}>
          <Label>{title}</Label>
          <div className="band-spacer" />
          {actions}
        </div>
      ) : null}
      {children}
    </div>
  );
}

/* ── NumberedGutter ───────────────────────────────────────────────────────── */

/**
 * A fixed-height numbered ruler with content on sparse lines — the readout idiom
 * from the reference film. The empty numerals are the point: they show the shape of
 * the whole checklist, so a run in progress reads as "4 of 30 done" at a glance
 * rather than as a list that happens to be four items long.
 */
export function NumberedGutter({
  lines,
  rows,
}: {
  lines: number;
  rows: Map<number, ReactNode>;
}) {
  return (
    <div className="gutter-list" role="list">
      {Array.from({ length: lines }, (_, i) => {
        const n = i + 1;
        const content = rows.get(n);
        return (
          <div key={n} style={{ display: "contents" }}>
            <div className="gutter-num" aria-hidden="true">
              {n}
            </div>
            <div className="gutter-row" role={content ? "listitem" : "presentation"}>
              {content ?? null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
