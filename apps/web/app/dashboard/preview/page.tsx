"use client";

/**
 * Secondary dashboard — DRAFT SURFACE, do not wire to real data yet.
 *
 * This page exists to finalise the look first: AcidSquares runs as the
 * full-bleed animated background (absolute, inset 0) and the working UI sits
 * above it on translucent glass panels so the background stays visible
 * between cards. Once the layout is signed off, real dashboard elements
 * (StageSteps, stat tiles, charts) get dropped into the placeholder slots.
 *
 * Honouring prefers-reduced-motion: the WebGL loop does not start (the
 * background stays a still dark field), so the page stays calm for people
 * who opt out of animation.
 */

import { useEffect, useState } from "react";

import AcidSquares from "../../../components/backgrounds/AcidSquares";
import DashboardTopBar from "../../../components/DashboardTopBar";

/** Placeholder card — replaced by real elements during integration. */
function GlassCard({
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
      className={`glass-card ${span}`.trim()}
      style={{ minHeight: height }}
    >
      <header className="glass-card-head">
        <span className="glass-card-title">{title}</span>
        <span className="mono-chip">DRAFT</span>
      </header>
      {children ?? (
        <p className="glass-card-note">
          Placeholder — real element lands here after the layout is locked.
        </p>
      )}
    </section>
  );
}

/** The user's chosen background config, verbatim. */
const BG_PROPS = {
  color1: "#5227FF",
  color2: "#A855F7",
  color3: "#FFFFFF",
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
  opacity: 0.42,
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
              The next dashboard, on an animated field. Layout draft — real
              elements land here once the look is signed off.
            </p>
          </div>
          <div className="head-actions">
            <span className="gateway-chip">
              <i /> Layout preview · no live data
            </span>
          </div>
        </div>

        <div className="preview-grid">
          <GlassCard title="MISSION OVERVIEW" span="col-span-2" height={220}>
            <div className="glass-draft-row">
              <div className="glass-tile">
                <span>MISSION ID</span>
                <b>—</b>
              </div>
              <div className="glass-tile">
                <span>AOI</span>
                <b>—</b>
              </div>
              <div className="glass-tile">
                <span>RESULT</span>
                <b>—</b>
              </div>
              <div className="glass-tile">
                <span>STATUS</span>
                <b>IDLE</b>
              </div>
            </div>
          </GlassCard>

          <GlassCard title="RUN STEPS" height={220}>
            <p className="glass-card-note">
              Slot for the JellyRadio step strip.
            </p>
          </GlassCard>

          <GlassCard title="CHANGE METRICS" height={180}>
            <div className="glass-draft-row">
              <div className="glass-tile">
                <span>FLOODED AREA</span>
                <b>—</b>
              </div>
              <div className="glass-tile">
                <span>CONFIDENCE</span>
                <b>—</b>
              </div>
            </div>
          </GlassCard>

          <GlassCard title="SENSOR" height={180}>
            <p className="glass-card-note">Slot for SensorCard.</p>
          </GlassCard>

          <GlassCard title="EVIDENCE" span="col-span-2" height={180}>
            <p className="glass-card-note">Slot for EvidencePanel.</p>
          </GlassCard>

          <GlassCard title="MONITORING" height={180}>
            <p className="glass-card-note">Slot for MonitoringCard.</p>
          </GlassCard>
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
