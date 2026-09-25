"use client";

/**
 * Dashboard — Srushti's mission-console UI wired to the live P1 Gateway.
 *
 * Architecture:
 *  - All layout, styling, and component structure from Srushti (feat/p5-mission-console)
 *  - Live backend wiring via `useMissionRun` hook from Atharv (feat/p5-frontend-migration)
 *  - No setTimeout, no mocks, no hardcoded state — backend drives everything
 */

import { useState, useEffect } from "react";
import { Globe2, Menu, PanelRightClose, PanelRightOpen, RefreshCw } from "lucide-react";

import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import MapCanvas from "./MapCanvas";
import QueryConsole from "./QueryConsole";
import ConfidenceCard from "./ConfidenceCard";
import EvidencePanel from "./EvidencePanel";
import RunTimeline from "./RunTimeline";
import SensorCard from "./SensorCard";
import MonitoringCard from "./MonitoringCard";
import ReportCard from "./ReportCard";
import TraceDrawer from "./TraceDrawer";
import { demoModeEnabled } from "../lib/api/source";

import { useMissionRun } from "../lib/useMissionRun";
import type { Stage, Evidence } from "../lib/types";

// ── Constants ──────────────────────────────────────────────────────────────────

const INITIAL_QUERY =
  "Analyse flood extent change in Assam, India over the past 30 days using SAR data";

/** Map a live RunStageView state → Srushti's StageStatus type */
function mapStageState(state: string): Stage["status"] {
  switch (state) {
    case "completed": return "done";
    case "running": return "active";
    case "failed": return "error";
    case "warning": return "warning";
    default: return "pending";
  }
}

/** Derive Srushti's Stage[] from the live useMissionRun stages */
function liveToStages(runStages: ReturnType<typeof useMissionRun>["stages"]): Stage[] {
  return runStages.map((s) => ({
    key: s.key,
    label: s.label,
    detail: s.detail,
    status: mapStageState(s.state),
  }));
}

/** Extract evidence items from the agent's final state (published after COMPLETED). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractEvidence(agentState: any): Evidence[] {
  if (!agentState) return [];
  const raw = agentState.evidence ?? agentState.evidence_graph?.nodes ?? {};
  if (Array.isArray(raw)) return raw as Evidence[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return Object.entries(raw).map(([id, node]: [string, any]) => ({
    id,
    kind: node.node_type ?? "observation",
    title: node.label ?? id,
    source: node.source ?? "backend",
    detail: node.detail ?? "",
    status: node.confidence_score >= 0.7 ? "verified" : "pending",
    provenance: `trace: ${agentState.trace_id ?? "—"}`,
  }));
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  // Theme
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  // Nav
  const [active, setActive] = useState("mission");
  const [mobileNav, setMobileNav] = useState(false);
  const [rightRail, setRightRail] = useState(true);
  // Trace drawer
  const [trace, setTrace] = useState(false);
  // Query input
  const [query, setQuery] = useState(INITIAL_QUERY);

  // ── Live backend wiring ──────────────────────────────────────────────────────
  // Pass `false` for LIVE mode. Set to `true` for demo/offline mode.
  const DEMO_MODE = demoModeEnabled();
  const run = useMissionRun(DEMO_MODE);

  const confidence = run.agentState?.confidence_score ?? null;
  const evidence = extractEvidence(run.agentState);
  const stages = liveToStages(run.stages);

  const missionId = run.agentState?.mission_id ?? run.jobId ?? "—";
  const runId = run.traceId ?? run.jobId ?? "—";
  const location = run.agentState?.location ?? "—";
  const summary = run.agentState?.summary ?? (run.phase === "complete" ? "Analysis complete" : "—");
  const missionStatus =
    run.phase === "running" ? "running" :
    run.phase === "complete" ? "completed" :
    run.phase === "failed" ? "failed" : "idle";

  // ── Theme persistence ────────────────────────────────────────────────────────
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("satquery-theme", theme);
  }, [theme]);

  useEffect(() => {
    const saved = localStorage.getItem("satquery-theme") as "dark" | "light" | null;
    if (saved) setTheme(saved);
  }, []);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleRun = () => {
    if (run.phase === "running" || !query.trim()) return;
    run.start(query, null);
  };

  const handleReset = () => {
    run.reset();
    setQuery(INITIAL_QUERY);
  };

  const contentTitle =
    active === "mission" ? "Mission overview" :
    active === "map" ? "Map workspace" :
    active === "monitor" ? "Persistent monitoring" :
    active === "evidence" ? "Evidence chain" :
    active === "history" ? "Mission history" :
    "Reports & decision briefs";

  const contentSubtitle =
    active === "mission" ? "Flagship flood mission and evidence-first workflow" :
    active === "map" ? "Inspect AOI, observations, overlays and confidence layers" :
    active === "monitor" ? "Recurring acquisition, alerting and mission watch state" :
    active === "evidence" ? "Provenance, observations, model metadata and audit trace" :
    active === "history" ? "Temporal mission memory and prior runs" :
    "Decision briefs, report generation and export surfaces";

  return (
    <div className="app-shell">
      {/* Mobile nav overlay */}
      <div className={`mobile-nav ${mobileNav ? "open" : ""}`}>
        <Sidebar
          active={active}
          onSelect={(id) => { setActive(id); setMobileNav(false); }}
        />
      </div>

      {/* Desktop sidebar */}
      <div className="desktop-sidebar">
        <Sidebar active={active} onSelect={setActive} />
      </div>

      <main className="main">
        <Topbar
          theme={theme}
          onTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          runId={runId}
        />

        {/* Mobile topbar */}
        <div className="mobile-top">
          <button className="icon-btn" onClick={() => setMobileNav(true)}>
            <Menu size={17} />
          </button>
          <span>{contentTitle}</span>
        </div>

        <div className="content">
          {/* Page header */}
          <div className="page-head">
            <div>
              <div className="eyebrow">FLAGSHIP MISSION · FLOOD IMPACT</div>
              <h1>
                See what changed.
                <br />
                <span>Know why.</span>
              </h1>
              <p className="subtitle">
                A map-first command center for evidence-backed satellite
                intelligence. Plan the mission, inspect observations, arbitrate
                sensors, measure change, and keep every conclusion auditable.
              </p>
            </div>
            <div className="head-actions">
              <span className="gateway-chip">
                <i /> Gateway only · secured
              </span>
              <button className="primary-btn" onClick={handleReset}>
                <RefreshCw size={14} /> New mission
              </button>
            </div>
          </div>

          {/* Workspace mode label */}
          <div className="workspace-mode">
            <div>
              <b>{contentTitle}</b>
              <span>{contentSubtitle}</span>
            </div>
            <span className="mono-chip">P5 / {active.toUpperCase()}</span>
          </div>

          {/* Main workspace */}
          <div className="workspace">
            <div className="map-card">
              <MapCanvas />
            </div>

            {rightRail && (
              <div className="right-rail">
                <QueryConsole
                  value={query}
                  onChange={setQuery}
                  onRun={handleRun}
                  running={run.phase === "running"}
                  onReset={handleReset}
                />
                {/* Show confidence only once backend returns a value */}
                {confidence !== null && (
                  <ConfidenceCard confidence={confidence} />
                )}
                {/* Error state */}
                {run.phase === "failed" && run.error && (
                  <div className="error-banner">
                    ⚠ {run.error.message}
                    {run.error.trace_id && (
                      <span className="mono-chip" style={{ marginLeft: 8 }}>
                        {run.error.trace_id}
                      </span>
                    )}
                  </div>
                )}
                <EvidencePanel
                  evidence={evidence}
                  onTrace={() => setTrace(true)}
                />
              </div>
            )}

            <button
              className="rail-toggle"
              onClick={() => setRightRail(!rightRail)}
              title={rightRail ? "Hide analysis rail" : "Show analysis rail"}
            >
              {rightRail ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
            </button>
          </div>

          {/* Mission stats strip */}
          <div className="section-strip">
            <div>
              <span>MISSION ID</span>
              <b>{missionId}</b>
            </div>
            <div>
              <span>AOI</span>
              <b>{location}</b>
            </div>
            <div>
              <span>RESULT</span>
              <b>{summary}</b>
            </div>
            <div>
              <span>CONFIDENCE</span>
              <b>{confidence !== null ? `${Math.round(confidence * 100)}%` : "—"}</b>
            </div>
            <div>
              <span>STATUS</span>
              <b className={missionStatus === "failed" ? "error-text" : "success-text"}>
                {missionStatus === "running"
                  ? "RUNNING"
                  : missionStatus === "completed"
                  ? "EVIDENCE READY"
                  : missionStatus === "failed"
                  ? "FAILED"
                  : "IDLE"}
              </b>
            </div>
          </div>

          {/* Bottom grid */}
          <div className="bottom-grid">
            <RunTimeline stages={stages} />
            <SensorCard />
            <MonitoringCard />
            <ReportCard onReport={() => setActive("reports")} />
          </div>

          <footer className="app-footer">
            <div>
              <Globe2 size={14} />
              <b>SatQuery AI</b>
              <span>Evidence-first satellite intelligence</span>
            </div>
            <div>
              <span>Gateway-only browser access</span>
              <span>•</span>
              <span>Traceable outputs</span>
              <span>•</span>
              <span>Accessible UI</span>
            </div>
          </footer>
        </div>
      </main>

      {/* Trace drawer (uses live stages from backend) */}
      {trace && (
        <TraceDrawer
          stages={stages}
          runId={runId}
          onClose={() => setTrace(false)}
        />
      )}

      <div className="mobile-nav-overlay" onClick={() => setMobileNav(false)} />
    </div>
  );
}
