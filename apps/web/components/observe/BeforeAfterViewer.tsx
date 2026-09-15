"use client";

/**
 * Before/after comparison (P5-07).
 *
 * The imagery dominates: metadata is a thin band under it, not a card around it.
 * A draggable divider wipes between the two scenes, and the handle is a real
 * <input type="range"> underneath a drawn divider, so the comparison is operable
 * from the keyboard with arrow keys and announced to a screen reader — a
 * pointer-only wipe is the usual way this control fails accessibility (P5-15).
 *
 * The `before` half is nullable. Single-date datasets genuinely have no pre-event
 * scene, and this renders that state explicitly rather than duplicating the after
 * image or leaving a grey box.
 */

import { useId, useState } from "react";

import { formatUTC } from "../../lib/geo/format";
import { Label, StatusChip } from "../system/primitives";
import type { ComparisonPair } from "../../lib/model/console";

export function BeforeAfterViewer({
  pair,
  beforeLabel = "Before",
  afterLabel = "After",
}: {
  pair: ComparisonPair;
  beforeLabel?: string;
  afterLabel?: string;
}) {
  const [split, setSplit] = useState(50);
  const sliderId = useId();
  const { before, after } = pair;

  return (
    <div>
      <div
        style={{
          position: "relative",
          aspectRatio: "1 / 1",
          background: "var(--void)",
          overflow: "hidden",
          borderBottom: "1px solid var(--hairline)",
        }}
      >
        {/* After fills the frame; before is clipped over it. */}
        {after.imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={after.imageUrl}
            alt={`${afterLabel}: ${after.imageDescription}`}
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <Missing text="No observation imagery" />
        )}

        {before?.imageUrl ? (
          <div
            style={{
              position: "absolute",
              inset: 0,
              clipPath: `inset(0 ${100 - split}% 0 0)`,
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={before.imageUrl}
              alt={`${beforeLabel}: ${before.imageDescription}`}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </div>
        ) : null}

        {before?.imageUrl ? (
          <>
            <div
              aria-hidden="true"
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `${split}%`,
                width: 1,
                background: "var(--signal)",
              }}
            />
            <input
              id={sliderId}
              type="range"
              min={0}
              max={100}
              value={split}
              onChange={(e) => setSplit(Number(e.target.value))}
              aria-label={`Comparison wipe. ${split}% ${beforeLabel}, ${100 - split}% ${afterLabel}.`}
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                opacity: 0,
                cursor: "ew-resize",
              }}
            />
          </>
        ) : null}

        <Corner side="left">
          {before ? beforeLabel : `${beforeLabel} — not available`}
        </Corner>
        <Corner side="right">{afterLabel}</Corner>
      </div>

      {!before && pair.beforeUnavailableReason ? (
        <div
          className="panel-section"
          role="note"
          style={{ borderLeft: "2px solid var(--amber)" }}
        >
          <div className="row" style={{ marginBottom: 4 }}>
            <StatusChip tone="warn">No pre-event scene</StatusChip>
          </div>
          <p style={{ margin: 0, fontSize: 11.5, color: "var(--ink-dim)", lineHeight: 1.5 }}>
            {pair.beforeUnavailableReason}
          </p>
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
        <SceneMeta title={beforeLabel} obs={before} />
        <SceneMeta title={afterLabel} obs={after} bordered />
      </div>
    </div>
  );
}

function Corner({ side, children }: { side: "left" | "right"; children: React.ReactNode }) {
  return (
    <span
      className="label"
      style={{
        position: "absolute",
        top: 8,
        [side]: 8,
        background: "rgba(0,0,0,0.65)",
        padding: "2px 6px",
        color: "var(--ink)",
      }}
    >
      {children}
    </span>
  );
}

function Missing({ text }: { text: string }) {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "grid",
        placeItems: "center",
      }}
    >
      <span className="label label-faint">{text}</span>
    </div>
  );
}

function SceneMeta({
  title,
  obs,
  bordered,
}: {
  title: string;
  obs: import("../../lib/model/console").Observation | null;
  bordered?: boolean;
}) {
  return (
    <div
      style={{
        padding: 8,
        borderLeft: bordered ? "1px solid var(--hairline)" : undefined,
      }}
    >
      <Label>{title}</Label>
      {!obs ? (
        <p className="readout-value readout-value-na" style={{ marginTop: 4 }}>
          NOT AVAILABLE
        </p>
      ) : (
        <div style={{ marginTop: 4 }}>
          <Row k="Sensor" v={obs.sensor} />
          <Row
            k="Acquired"
            v={obs.acquired ? formatUTC(obs.acquired) : null}
            reason={obs.acquiredUnavailableReason}
          />
          <Row k="Dataset" v={obs.dataset} />
          <Row k="GSD" v={obs.resolutionM ? `${obs.resolutionM} m` : null} />
          <Row
            k="Cloud"
            v={obs.cloudFraction === null ? null : `${Math.round(obs.cloudFraction * 100)}%`}
            reason="Cloud fraction does not apply to SAR."
          />
        </div>
      )}
    </div>
  );
}

function Row({ k, v, reason }: { k: string; v: string | null; reason?: string }) {
  return (
    <div className="readout" style={{ minHeight: 17 }}>
      <Label faint>{k}</Label>
      {v ? (
        <span className="readout-value" style={{ fontSize: 10 }}>
          {v}
        </span>
      ) : (
        <span
          className="readout-value readout-value-na"
          style={{ fontSize: 10 }}
          title={reason ?? "Not supplied."}
        >
          N/A
        </span>
      )}
    </div>
  );
}
