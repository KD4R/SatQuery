"use client";

/**
 * Step-by-step beginner's guide — a floating panel the user can collapse and
 * drag anywhere on the page, or hide for the rest of the browser session. The drag handle is the header; position is
 * clamped to the viewport and re-clamped on resize. Steps are one-liners that
 * point only at controls that actually exist — no invented figures.
 *
 * The visuals live on the React Bits BorderGlow card inside: its mesh-gradient
 * border follows the cursor and intensifies near the panel's edges. This
 * section only positions the panel and hosts the drag handlers.
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
  X,
} from "lucide-react";

import BorderGlow from "./system/BorderGlow";

type GuideStep = { icon: React.ReactNode; title: string; body: string };

/** Live mode: nothing is preloaded, so the guide starts with the AOI. */
const LIVE_STEPS: GuideStep[] = [
  {
    icon: <PenLine size={15} />,
    title: "1 · Aim",
    body: "Search a place on the map, then Draw AOI or Rectangle around it.",
  },
  {
    icon: <MousePointerClick size={15} />,
    title: "2 · Ask",
    body: "Type the question. Dates are optional; empty searches the last 90 days.",
  },
  {
    icon: <Play size={15} />,
    title: "3 · Run",
    body: "Press Enter. Each step lights up as the backend finishes it.",
  },
  {
    icon: <FileSearch size={15} />,
    title: "4 · Read",
    body: "The result card gives the area and its confidence; the water outline is drawn on the map.",
  },
  {
    icon: <ListOrdered size={15} />,
    title: "5 · Verify",
    body: "Scroll down for WHY, the evidence chain and what was searched; Trace has the ids.",
  },
];

/** Demo mode: the pinned Assam AOI is preloaded. */
const DEMO_STEPS: GuideStep[] = [
  {
    icon: <Play size={15} />,
    title: "1 · Run",
    body: "The demo AOI is preloaded. Press Run to replay the pinned analysis.",
  },
  {
    icon: <ListOrdered size={15} />,
    title: "2 · Read",
    body: "Steps settle one by one; one is amber because half the AOI was unseen.",
  },
  {
    icon: <FileSearch size={15} />,
    title: "3 · Verify",
    body: "Scroll down for the intelligence panel; WHY GRAPH opens the evidence chain.",
  },
  {
    icon: <BellRing size={15} />,
    title: "4 · Scrub",
    body: "The time machine on the map steps Before → After → Change.",
  },
];

/** Dismissal is remembered for the browser tab only (a UI preference, not data). */
const DISMISS_KEY = "sq-guide-dismissed";

const MARGIN = 12;

export default function BeginnerGuide({ demo = false }: { demo?: boolean }) {
  const STEPS = demo ? DEMO_STEPS : LIVE_STEPS;
  const [open, setOpen] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  useEffect(() => {
    try {
      if (sessionStorage.getItem(DISMISS_KEY) === "1") setDismissed(true);
    } catch {
      /* storage unavailable: the guide simply shows */
    }
  }, []);
  const dismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* ignore */
    }
  };
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

  if (dismissed) return null;

  return (
    <section
      ref={panelRef}
      className={`guide-float${dragging ? " is-dragging" : ""}`}
      style={style}
      data-open={open}
      aria-label="Step by step guide"
    >
      <BorderGlow
        edgeSensitivity={30}
        glowColor="40 80 80"
        backgroundColor="#120F17"
        borderRadius={28}
        glowRadius={40}
        glowIntensity={1.0}
        coneSpread={25}
        animated={false}
        colors={["#c084fc", "#f472b6", "#38bdf8"]}
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
          <button
            type="button"
            className="guide-toggle"
            onClick={dismiss}
            aria-label="Hide guide for this session"
            title="Hide for this session"
          >
            <X size={15} />
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
      </BorderGlow>
    </section>
  );
}
