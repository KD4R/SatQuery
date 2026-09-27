"use client";

/**
 * Secondary dashboard — DRAFT SURFACE, do not wire to real data yet.
 *
 * Styled after the landing page's instrument palette (space.css): near-black
 * ground, slate raise-steps with hairlines, signal orange as the one accent,
 * Share Tech Mono for anything measured. AcidSquares runs behind it, retuned
 * to the same hues so the field reads as part of the product rather than a
 * demo of the library.
 *
 * Honouring prefers-reduced-motion: the WebGL loop does not start (the
 * background stays a still dark field).
 */

import { useEffect, useState } from "react";

import AcidSquares from "../../../components/backgrounds/AcidSquares";
import DashboardTopBar from "../../../components/DashboardTopBar";

/** Placeholder card — replaced by real elements during integration. */
function DraftCard({
  title,
  span = "",
  height = 160,
  children,
}: {
  title: string;
  span?: string;
  height?: number;
  children?: React.ReactNode;
}) {
  return (
    <section
      className={`draft-card ${span}`.trim()}
      style={{ minHeight: height }}
    >
      <header className="draft-card-head">
        <span className="draft-card-title">{title}</span>
        <span className="draft-chip">DRAFT</span>
      </header>
      {children ?? (
        <p className="draft-note">
          Placeholder — real element lands here after the layout is locked.
        </p>
      )}
    </section>
  );
}

/**
 * The user's chosen background config, retuned from the purple demo palette to
 * the landing's instrument hues: the ray-marched energy reads signal orange
 * rising through data-blue, on the near-black ground. opacity/exposure sit
 * below the library defaults so panel text stays readable.
 */
const BG_PROPS = {
  color1: "#0e0f10",
  color2: "#60a0f8",
  color3: "#f87010",
  detail: "medium" as const,
  speed: 0.7,
  waveDepth: 1,
  zoom: 1.3,
  density: 10.0,
  glow: 1.0,
  exposure: 1600,
  spread: 0.3,
  stepSize: 0.002,
  colorShift: 0,
  contrast: 1,
  brightness: 1.0,
  opacity: 0.45,
  mouseInteraction: true,
  mouseStrength: 0.1,
  mouseRadius: 0.35,
  blur: 0,
  grain: true,
  grainIntensity: 0.05,
};

export default function DashboardPreviewPage() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReducedMotion(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  return (
    <main className="preview-shell">
      {/* Animated background — fixed, behind everything. */}
      <div className="preview-bg" aria-hidden="true">
        {reducedMotion ? null : <AcidSquares {...BG_PROPS} />}
      </div>

      <DashboardTopBar activeHref="/dashboard/preview" />
      <div className="preview-content">
        <div className="page-head">
          <div>
            <div className="eyebrow">DRAFT · SECONDARY DASHBOARD</div>
            <h1>
              Mission surface,
              <br />
              <span>reimagined.</span>
            </h1>
            <p className="subtitle">
              The next dashboard, on the landing&apos;s instrument palette. Layout
              draft — real elements land here once the look is signed off.
            </p>
          </div>
          <div className="head-actions">
            <span className="gateway-chip">
              <i /> Layout preview · no live data
            </span>
          </div>
        </div>

        <div className="preview-grid">
          <DraftCard title="MISSION OVERVIEW" span="col-span-2" height={220}>
            <div className="draft-row">
              <div className="draft-tile">
                <span>MISSION ID</span>
                <b>—</b>
              </div>
              <div className="draft-tile">
                <span>AOI</span>
                <b>—</b>
              </div>
              <div className="draft-tile">
                <span>RESULT</span>
                <b>—</b>
              </div>
              <div className="draft-tile">
                <span>STATUS</span>
                <b className="draft-tile-accent">IDLE</b>
              </div>
            </div>
          </DraftCard>

          <DraftCard title="RUN STEPS" height={220}>
            <p className="draft-note">Slot for the JellyRadio step strip.</p>
          </DraftCard>

          <DraftCard title="CHANGE METRICS" height={200}>
            <div className="draft-row">
              <div className="draft-tile">
                <span>FLOODED AREA</span>
                <b>—</b>
              </div>
              <div className="draft-tile">
                <span>CONFIDENCE</span>
                <b>—</b>
              </div>
            </div>
          </DraftCard>

          <DraftCard title="SENSOR" height={200}>
            <p className="draft-note">Slot for SensorCard.</p>
          </DraftCard>

          <DraftCard title="EVIDENCE" span="col-span-2" height={200}>
            <p className="draft-note">Slot for EvidencePanel.</p>
          </DraftCard>

          <DraftCard title="MONITORING" height={200}>
            <p className="draft-note">Slot for MonitoringCard.</p>
          </DraftCard>
        </div>

        <footer className="app-footer">
          <div>
            <b>SatQuery AI</b>
            <span>Draft dashboard · background experiment</span>
          </div>
        </footer>
      </div>
    </main>
  );
}
