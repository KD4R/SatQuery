"use client";

/**
 * Step-by-step beginner's guide — a floating panel the user can collapse and
 * drag anywhere on the page. The drag handle is the header; position is
 * clamped to the viewport and re-clamped on resize. Steps are one-liners that
 * point only at controls that actually exist — no invented figures.
 */

import { useEffect, useRef, useState } from "react";
import {
  BellRing,
  ChevronDown,
  ChevronRight,
  FileSearch,
  ListOrdered,
  MousePointerClick,
  PenLine,
  Play,
} from "lucide-react";

const STEPS: { icon: React.ReactNode; title: string; body: string }[] = [
  {
    icon: <MousePointerClick size={15} />,
    title: "1 · Ask",
    body: "Type your question in MISSION COPILOT — plain language works.",
  },
  {
    icon: <PenLine size={15} />,
    title: "2 · Aim",
    body: "DRAW AOI outlines your own area; the demo AOI starts preloaded.",
  },
  {
    icon: <Play size={15} />,
    title: "3 · Run",
    body: "Press ENTER. The step list under the query tracks the backend live.",
  },
  {
    icon: <ListOrdered size={15} />,
    title: "4 · Read",
    body: "The highlighted step is processing; metrics fill when it completes.",
  },
  {
    icon: <FileSearch size={15} />,
    title: "5 · Verify",
    body: "WHY? EVIDENCE CHAIN explains each claim; Trace opens the audit.",
  },
  {
    icon: <BellRing size={15} />,
    title: "6 · Watch",
    body: "Monitoring re-runs the watch on a schedule; Reports exports it.",
  },
];

const MARGIN = 12;

export default function BeginnerGuide() {
  const [open, setOpen] = useState(true);
  // null = docked bottom-right (CSS default); otherwise free-dragged position.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const panelRef = useRef<HTMLElement | null>(null);
  const grabRef = useRef<{ dx: number; dy: number } | null>(null);

  const clamp = (x: number, y: number) => {
    const el = panelRef.current;
    const w = el?.offsetWidth ?? 340;
    return {
      x: Math.min(Math.max(MARGIN, x), Math.max(MARGIN, window.innerWidth - w - MARGIN)),
      y: Math.min(Math.max(MARGIN, y), Math.max(MARGIN, window.innerHeight - 44 - MARGIN)),
    };
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest("button")) return; // toggle stays a button
    const el = panelRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    grabRef.current = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const g = grabRef.current;
    if (!g) return;
    setPos(clamp(e.clientX - g.dx, e.clientY - g.dy));
  };

  const endDrag = () => {
    grabRef.current = null;
    setDragging(false);
  };

  // Keep the panel on-screen when the window shrinks.
  useEffect(() => {
    if (!pos) return;
    const onResize = () => setPos((p) => (p ? clamp(p.x, p.y) : p));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [pos]);

  const style = pos
    ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" }
    : undefined;

  return (
    <section
      ref={panelRef}
      className={`guide-float${dragging ? " is-dragging" : ""}`}
      style={style}
      data-open={open}
      aria-label="Step by step guide"
    >
      <div
        className="guide-head"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <span className="guide-grip" aria-hidden="true">
          ⠿
        </span>
        <span className="guide-index" aria-hidden="true">
          ?
        </span>
        <b>Step by step guide</b>
        <button
          type="button"
          className="guide-toggle"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={open ? "Collapse guide" : "Expand guide"}
        >
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      {open && (
        <ol className="guide-body">
          {STEPS.map((s) => (
            <li className="guide-item" key={s.title}>
              <span className="guide-icon">{s.icon}</span>
              <span className="guide-text">
                <b>{s.title}</b>
                <small>{s.body}</small>
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
