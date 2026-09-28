"use client";

/**
 * The mission console — the one canonical console (ROUTES.console = /dashboard).
 *
 * This is where the landing page's Console button lands. It composes:
 *   - the copilot query box and the plan it resolved to (P5-03),
 *   - the run's step list, driven only by what the backend reports (P5-04),
 *   - the MapLibre workspace with AOI draw/edit/validation and the Earth Time
 *     Machine (P5-05..08),
 *   - the intelligence section: change, confidence, WHY, sensors, impact (P5-08..11),
 *   - the agent-activity toasts (P5 §2C) and entry points to monitoring and reports.
 *
 * Demo and live are chosen once, from lib/api/source. In demo the scenario comes
 * from lib/fixtures and every fixture-fed surface carries the fixture badge; in
 * live the intelligence section shows only what the agent published and never
 * falls back to a fixture, because doing that silently would be fabricating success.
 */

import dynamic from "next/dynamic";
import { useCallback, useMemo, useState } from "react";
import { Globe2, PanelRightClose, PanelRightOpen } from "lucide-react";

import PageTelemetry from "./PageTelemetry";
import BeginnerGuide from "./BeginnerGuide";
import MapCanvas from "./MapCanvas";
import QueryConsole from "./QueryConsole";
import PlanParameters from "./PlanParameters";
import ConfidenceCard from "./ConfidenceCard";
import EvidencePanel from "./EvidencePanel";
import LiveSummary from "./LiveSummary";
import StageList from "./StageList";
import MonitoringCard from "./MonitoringCard";
import ReportCard from "./ReportCard";
import TraceDrawer from "./TraceDrawer";
import DashboardTopBar from "./DashboardTopBar";
import { AgentActivityToasts } from "./console/AgentActivityToasts";
import { ErrorBoundary } from "./system/ErrorBoundary";
import { ProvenanceBadge } from "./system/primitives";
import type { LayerId } from "./map/MapWorkspace";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../lib/fixtures";
import { useMissionRun } from "../lib/useMissionRun";
import { useAgentActivity } from "../lib/useAgentActivity";
import { demoModeEnabled, type DataSource } from "../lib/api/source";
import { validateAOI } from "../lib/geo/validate";
import { ROUTES } from "../lib/nav";
import type { GeoJSONPolygon } from "../lib/api/types";
import type { Stage, Evidence } from "../lib/types";

/**
 * The intelligence section (imagery viewer, impact model, evidence graph loader)
 * only matters once a run completes, so it stays out of the first-load bundle
 * (P5-16).
 */
const IntelligencePanel = dynamic(
  () => import("./evidence/IntelligencePanel").then((m) => m.IntelligencePanel),
  {
    ssr: false,
    loading: () => (
      <span className="label label-faint">Loading intelligence…</span>
    ),
  },
);

// ── Constants ──────────────────────────────────────────────────────────────────

const LIVE_INITIAL_QUERY =
  "Analyse flood extent change in Assam, India over the past 30 days using SAR data";

const INITIAL_LAYERS = (demo: boolean): Record<LayerId, boolean> => ({
  observation: true,
  // The demo's Time Machine epochs fall under this category; the rail needs it
  // on to show "Before". Live mode keeps it off until the operator asks.
  baseline: demo,
  change: true,
  confidence: false,
  aoi: true,
});

/** Map a live RunStageView state → the step list's StageStatus type */
function mapStageState(state: string): Stage["status"] {
  switch (state) {
    case "completed": return "done";
    case "running": return "active";
    case "failed": return "error";
    // A stage that finished having seen less than half the AOI is neither done
    // nor failed; it stays visibly amber.
    case "degraded":
    case "warning": return "warning";
    default: return "pending";
  }
}

/** Derive the step list's Stage[] from the live useMissionRun stages */
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
  const demo = demoModeEnabled();
  const source: DataSource = demo ? "fixture" : "gateway";

  // Right rail
  const [rightRail, setRightRail] = useState(true);
  // Trace drawer
  const [trace, setTrace] = useState(false);
  // Query + AOI. The demo opens on the pinned scenario's own query and AOI so the
  // question and the polygon agree; live starts with no AOI drawn.
  const [query, setQuery] = useState(demo ? ASSAM_SCENARIO.query : LIVE_INITIAL_QUERY);
  const [aoi, setAoi] = useState<GeoJSONPolygon | null>(
    demo ? ASSAM_SCENARIO.aoi : null,
  );
  const [layers, setLayers] = useState<Record<LayerId, boolean>>(() =>
    INITIAL_LAYERS(demo),
  );

  // ── Run wiring ───────────────────────────────────────────────────────────────
  // One run drives the whole page. The demo flag is read through lib/api/source
  // like everywhere else — one audited switch, per the fixture-isolation rule.
  const run = useMissionRun(demo);
  const activity = useAgentActivity(demo, run);

  const complete = run.phase === "complete";
  const validation = useMemo(() => validateAOI(aoi), [aoi]);
  const toggleLayer = useCallback((id: LayerId) => {
    setLayers((l) => ({ ...l, [id]: !l[id] }));
  }, []);

  // A drawn AOI that is invalid blocks the run. No AOI at all does not: the
  // request may name its area in words, and refusing it here would stop the
  // natural-language flow before the backend has had a say.
  const blockedReason =
    query.trim().length === 0
      ? "Enter a mission query."
      : aoi !== null && !validation.valid
        ? (validation.findings.find((f) => f.severity === "error")?.message ??
          "The AOI is invalid.")
        : null;

  const agentState = run.agentState;
  const confidence = agentState?.confidence_score ?? null;
  const evidence = extractEvidence(agentState);
  const stages = liveToStages(run.stages);

  const missionId = demo
    ? run.phase === "idle"
      ? "—"
      : ASSAM_SCENARIO.missionId
    : (agentState?.mission_id ?? run.missionId ?? run.jobId ?? "—");
  const runId = run.traceId ?? run.jobId ?? "—";
  const reportMissionId = complete
    ? demo
      ? ASSAM_SCENARIO.missionId
      : (agentState?.mission_id ?? run.missionId)
    : null;
  // MissionState publishes no location/summary fields — show what exists, "—"
  // where nothing does, rather than reading fields the backend never sends.
  const location = demo
    ? ASSAM_SCENARIO.aoiName
    : agentState?.aoi
      ? "AOI validated"
      : "—";
  const summary = complete ? "Analysis complete" : "—";
  const missionStatus =
    run.phase === "running" ? "running" :
    run.phase === "complete" ? "completed" :
    run.phase === "failed" ? "failed" : "idle";

  const parameters = useMemo(
    () => ({
      aoiName: demo ? ASSAM_SCENARIO.aoiName : aoi ? "Operator-drawn AOI" : null,
      aoiAreaSqM: validation.areaSqM,
      dateRange:
        complete && demo
          ? "Latest pass vs permanent baseline"
          : complete && agentState?.temporal_window
            ? `${agentState.temporal_window.start} → ${agentState.temporal_window.end}`
            : null,
      sensors:
        complete && demo
          ? ["SENTINEL-1"]
          : complete
            ? (agentState?.selected_sensors ?? [])
            : [],
      resolutionM: complete && demo ? 10 : null,
      analysisType: complete && demo ? "Surface-water change" : null,
      inferred: new Set(
        complete && demo ? ["dateRange", "sensors", "analysisType"] : [],
      ),
    }),
    [demo, aoi, validation.areaSqM, complete, agentState],
  );

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleRun = () => {
    if (run.phase === "running" || blockedReason) return;
    run.start(query, aoi);
  };

  const handleReset = () => {
    run.reset();
    setQuery(demo ? ASSAM_SCENARIO.query : LIVE_INITIAL_QUERY);
    setAoi(demo ? ASSAM_SCENARIO.aoi : null);
  };

  // Single nav bar (brand + section chips + icon actions); telemetry sits at
  // the bottom of the page. The opening view is the mission page.
  return (
    <>
      <DashboardTopBar activeHref={ROUTES.console} />
      <div className="app-shell app-shell--flat">
      <main className="main" id="mission-main" tabIndex={-1}>

        <div className="content">
          {/* Workspace label — bigger, left-aligned */}
          <div className="workspace-mode mission-head">
            <div>
              <h1 className="mission-title">Mission overview</h1>
              <span>Flagship flood mission and evidence-first workflow</span>
            </div>
            <span className="mono-chip">P5 / MISSION</span>
          </div>

          {/* Main workspace — query rail left, map right */}
          <div className="workspace">
            {rightRail && (
              <div className="right-rail">
                <ErrorBoundary area="Mission panel">
                  <QueryConsole
                    value={query}
                    onChange={setQuery}
                    onRun={handleRun}
                    running={run.phase === "running"}
                    onReset={handleReset}
                    blockedReason={blockedReason}
                  />
                  <PlanParameters parameters={parameters} aoiValidation={validation} />
                  {/* Vertical step list directly under the query input */}
                  <StageList stages={stages} />
                  {/* Error state */}
                  {run.phase === "failed" && run.error && (
                    <div className="error-banner" role="alert">
                      ⚠ {run.error.message}
                      {run.error.trace_id && (
                        <span className="mono-chip" style={{ marginLeft: 8 }}>
                          {run.error.trace_id}
                        </span>
                      )}
                    </div>
                  )}
                </ErrorBoundary>
              </div>
            )}

            <div className="map-card">
              {/* The run this Dashboard drives (demo or live) is the same one
                  the map card observes — one run, one source of truth. */}
              <ErrorBoundary area="Map">
                <MapCanvas
                  complete={complete}
                  aoi={aoi}
                  onAoiChange={setAoi}
                  visible={layers}
                  onToggleLayer={toggleLayer}
                />
              </ErrorBoundary>
            </div>

            <button
              className="rail-toggle"
              onClick={() => setRightRail(!rightRail)}
              aria-label={rightRail ? "Hide analysis rail" : "Show analysis rail"}
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
              <b>
                {demo && complete
                  ? `${Math.round(ASSAM_SCENARIO.confidence.score * 100)}%`
                  : confidence !== null
                    ? `${Math.round(confidence * 100)}%`
                    : "—"}
              </b>
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

          {/* Intelligence — change, confidence, WHY, sensors, impact. Demo reads
              the pinned scenario; live reads only what the agent published. */}
          <section className="intel-section" aria-label="Intelligence">
            <ErrorBoundary area="Intelligence panel">
              {demo ? (
                <IntelligencePanel
                  scenario={complete ? ASSAM_SCENARIO : null}
                  source={source}
                  sourceAt={FIXTURE_EPOCH}
                  revealed={complete}
                  aoiAreaSqM={validation.areaSqM}
                />
              ) : complete && agentState ? (
                <div className="intel-live">
                  <ConfidenceCard
                    confidence={confidence}
                    reasons={agentState.uncertainty_reasons ?? []}
                  />
                  <LiveSummary state={agentState} />
                  <EvidencePanel evidence={evidence} onTrace={() => setTrace(true)} />
                </div>
              ) : (
                <section className="card">
                  <div className="card-head">
                    <div>
                      <div className="card-title">INTELLIGENCE</div>
                      <div className="card-sub">
                        No analysis yet. Run a mission to populate this section;
                        nothing is shown before the backend has produced it.
                      </div>
                    </div>
                    {demo ? <ProvenanceBadge source="fixture" at={FIXTURE_EPOCH} /> : null}
                  </div>
                </section>
              )}
            </ErrorBoundary>
          </section>

          {/* Next actions */}
          <div className="bottom-grid bottom-grid--two">
            <MonitoringCard />
            <ReportCard missionId={reportMissionId} />
          </div>

          {/* Beginner guide */}
          <BeginnerGuide />

          <PageTelemetry run={run} />

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

      {/* Agent activity toasts float bottom-right over everything (P5 §2C). */}
      <AgentActivityToasts events={activity.events} onDismiss={activity.dismiss} />

      {/* Trace drawer (uses live stages from backend) */}
      {trace && (
        <TraceDrawer
          stages={stages}
          runId={runId}
          onClose={() => setTrace(false)}
        />
      )}

      </div>
    </>
  );
}
