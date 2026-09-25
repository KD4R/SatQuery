"use client";

/**
 * The fullscreen three-zone layout (P5-01).
 *
 *   ┌─ telemetry bands ───────────────────────────┐
 *   │ query rail │      MAP (1fr)     │ intel rail │
 *   └─ status band ───────────────────────────────┘
 *
 * The map is the grid's only flexible column, so it takes every pixel the rails do
 * not. That is the structural reason the product reads as map-first rather than as
 * a dashboard that contains a map — the map is never given a fixed size and never
 * sits inside a card.
 *
 * Below 1100px the rails stop being columns and become overlay drawers over the
 * map, rather than shrinking. The PRD's mobile rule is that the map stays primary.
 */

import { useEffect, useState, type ReactNode } from "react";

import { Label } from "../system/primitives";

export interface MissionShellProps {
  telemetry: ReactNode;
  queryRail: ReactNode;
  map: ReactNode;
  intelRail: ReactNode;
  statusLeft?: ReactNode;
  statusRight?: ReactNode;
}

export function MissionShell({
  telemetry,
  queryRail,
  map,
  intelRail,
  statusLeft,
  statusRight,
}: MissionShellProps) {
  const [narrow, setNarrow] = useState(false);
  const [openRail, setOpenRail] = useState<"query" | "intel" | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1100px)");
    const apply = () => setNarrow(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  // Escape closes an open drawer — a drawer with no keyboard exit is a trap (P5-15).
  useEffect(() => {
    if (!openRail) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenRail(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openRail]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100dvh",
        background: "var(--void)",
      }}
    >
      {telemetry}

      <main
        id="mission-main"
        tabIndex={-1}
        style={{
          flex: "1 1 auto",
          minHeight: 0,
          display: "grid",
          gridTemplateColumns: narrow ? "1fr" : "var(--rail-w) 1fr var(--rail-w)",
        }}
      >
        {!narrow && (
          <div style={{ borderRight: "1px solid var(--hairline)", minHeight: 0 }}>
            {queryRail}
          </div>
        )}

        <div style={{ position: "relative", minHeight: 0, background: "var(--void)" }}>
          {map}

          {narrow && (
            <>
              <div
                style={{
                  position: "absolute",
                  top: 8,
                  left: 8,
                  right: 8,
                  display: "flex",
                  gap: 8,
                  zIndex: 5,
                }}
              >
                <button
                  className="btn"
                  onClick={() => setOpenRail("query")}
                  aria-expanded={openRail === "query"}
                >
                  Mission
                </button>
                <div className="band-spacer" />
                <button
                  className="btn"
                  onClick={() => setOpenRail("intel")}
                  aria-expanded={openRail === "intel"}
                >
                  Intelligence
                </button>
              </div>

              {openRail && (
                <div
                  role="dialog"
                  aria-modal="true"
                  aria-label={openRail === "query" ? "Mission panel" : "Intelligence panel"}
                  style={{
                    position: "absolute",
                    inset: 0,
                    zIndex: 10,
                    background: "var(--surface-1)",
                    display: "flex",
                    flexDirection: "column",
                  }}
                >
                  <div className="band">
                    <Label>{openRail === "query" ? "Mission" : "Intelligence"}</Label>
                    <div className="band-spacer" />
                    <button className="btn" onClick={() => setOpenRail(null)} autoFocus>
                      Close
                    </button>
                  </div>
                  <div style={{ flex: "1 1 auto", minHeight: 0 }}>
                    {openRail === "query" ? queryRail : intelRail}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {!narrow && (
          <div style={{ borderLeft: "1px solid var(--hairline)", minHeight: 0 }}>
            {intelRail}
          </div>
        )}
      </main>

      <footer className="band band-footer" style={{ height: 24 }}>
        {statusLeft}
        <div className="band-spacer" />
        {statusRight}
      </footer>
    </div>
  );
}
