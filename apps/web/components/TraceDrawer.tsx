"use client";

/**
 * The audit trace for the current run (audit F9, F10).
 *
 * A real modal dialog: role="dialog" with aria-modal, labelled by its heading,
 * focus moves in on open and is trapped while open, Escape closes, and focus
 * returns to whatever opened it. "Copy trace ID" writes to the clipboard and
 * "Export trace" downloads the run as JSON — both do what they say, or are not
 * shown.
 */

import { CheckCircle2, Copy, Download, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Stage } from "../lib/types";

export default function TraceDrawer({
  stages,
  runId,
  ids = {},
  exportPayload = null,
  onClose,
}: {
  stages: Stage[];
  runId: string;
  /** Correlation ids to show: trace, job, mission, inference trace. */
  ids?: Record<string, string | null | undefined>;
  /** What "Export trace" downloads (the run state). Hidden when null. */
  exportPayload?: unknown;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const panel = useRef<HTMLElement | null>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    opener.current = document.activeElement;
    const focusables = () =>
      Array.from(
        panel.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((el) => !el.hasAttribute("disabled"));
    focusables()[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (opener.current instanceof HTMLElement) opener.current.focus();
    };
  }, [onClose]);

  const copyId = async () => {
    try {
      await navigator.clipboard.writeText(runId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const exportTrace = () => {
    const blob = new Blob(
      [JSON.stringify({ run: runId, ids, stages, state: exportPayload }, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `satquery-trace-${runId.replace(/[^\w-]+/g, "_")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const idRows = Object.entries(ids).filter(([, v]) => Boolean(v)) as [string, string][];

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />
      <aside
        ref={panel}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="trace-title"
      >
        <div className="drawer-head">
          <div>
            <div className="eyebrow">AUDIT TRACE</div>
            <h2 id="trace-title">Run {runId}</h2>
          </div>
          <button className="close" onClick={onClose} aria-label="Close trace" type="button">
            <X size={17} />
          </button>
        </div>
        <div className="trace-intro">
          <CheckCircle2 size={15} />
          <span>Each step as the backend reported it, with the ids to find it in the logs.</span>
        </div>
        {idRows.length ? (
          <dl className="trace-ids">
            {idRows.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        <div className="trace">
          {stages.map((s) => (
            <div className="trace-row" key={s.key}>
              <div className="trace-stage">
                <b>{s.key}</b>
                <span>{s.status}</span>
              </div>
              <div>
                <strong>{s.label}</strong>
                <p>{s.detail}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="trace-footer">
          <button className="ghost-btn" onClick={copyId} type="button">
            <Copy size={13} /> {copied ? "Copied" : "Copy trace ID"}
          </button>
          {exportPayload !== null ? (
            <button className="ghost-btn" onClick={exportTrace} type="button">
              <Download size={13} /> Export trace
            </button>
          ) : null}
        </div>
      </aside>
    </>
  );
}
