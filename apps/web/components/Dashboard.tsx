"use client";

/**
 * The mission console — the one canonical console (ROUTES.console = /dashboard).
 *
 * Map-first (audit F1): the map fills the screen to the right of one rail that
 * holds the question, the answer and the run's steps. Detail — WHY, confidence,
 * evidence chain, what was searched — sits under the map, one scroll away.
 *
 * Demo and live are chosen once, from lib/api/source. In demo the scenario comes
 * from lib/fixtures and every fixture-fed surface carries the fixture badge; in
 * live every number comes from the agent's published run state (lib/live/result)
 * and never falls back to a fixture, because doing that silently would be
 * fabricating success.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Globe2, PanelLeftClose, PanelLeftOpen } from "lucide-react";

import PageTelemetry from "./PageTelemetry";
import BeginnerGuide from "./BeginnerGuide";
import MapCanvas from "./MapCanvas";
import QueryConsole, { dateRangeProblem } from "./QueryConsole";
import PlanParameters from "./PlanParameters";
import StageList from "./StageList";
import ReportCard from "./ReportCard";
import TraceDrawer from "./TraceDrawer";
import DashboardTopBar from "./DashboardTopBar";
import { AgentActivityToasts } from "./console/AgentActivityToasts";
import { ErrorBoundary } from "./system/ErrorBoundary";
import { ProvenanceBadge } from "./system/primitives";
import { FailureCard, IdleCard, LiveIntelligence, ResultCard, RunningCard } from "./dash/LivePanels";
import type { LayerId } from "./map/MapWorkspace";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../lib/fixtures";
import { useMissionRun } from "../lib/useMissionRun";
import { useAgentActivity } from "../lib/useAgentActivity";
import { demoModeEnabled, type DataSource } from "../lib/api/source";
import { validateAOI } from "../lib/geo/validate";
import { failureHint, toLiveResult } from "../lib/live/result";
import { useAnalysisExtent } from "../lib/live/useAnalysisExtent";
import { ROUTES } from "../lib/nav";
import type { GeoJSONPolygon, TemporalWindow } from "../lib/api/types";
import type { Stage } from "../lib/types";
import type { StepView } from "../lib/live/steps";

/**
 * The intelligence section (imagery viewer, impact model, evidence graph loader)
 * only matters once a run completes, so it stays out of the first-load bundle
 * (P5-16).
 */
const IntelligencePanel = dynamic(
  () => import("./evidence/IntelligencePanel").then((m) => m.IntelligencePanel),
  {
    ssr: false,
    loading: () => <span className="label label-faint">Loading intelligence…</span>,
  },
);

// ── Constants ──────────────────────────────────────────────────────────────────

const LIVE_INITIAL_QUERY = "Map the flood extent in the selected area and explain why you chose SAR.";

const INITIAL_LAYERS = (demo: boolean): Record<LayerId, boolean> => ({
  observation: true,
  // The demo's Time Machine epochs fall under this category; the rail needs it
  // on to show "Before".
  baseline: demo,
  change: true,
  confidence: false,
  aoi: true,
});

/** Map a run step state → the step list's StageStatus type */
function mapStageState(state: string): Stage["status"] {
  switch (state) {
    case "completed":
      return "done";
    case "running":
      return "active";
    case "failed":
      return "error";
    // A stage that finished having seen less than half the AOI is neither done
    // nor failed; it stays visibly amber.
    case "degraded":
    case "warning":
      return "warning";
    default:
      return "pending";
  }
}

function toStages(runStages: ReturnType<typeof useMissionRun>["stages"]): Stage[] {
  return runStages.map((s) => ({
    key: s.key,
    label: s.label,
    detail: s.detail,
    status: mapStageState(s.state),
  }));
}

/** Date inputs give whole days; the agent wants instants. */
function toWindow(dates: TemporalWindow | null): TemporalWindow | null {
  if (!dates || dateRangeProblem(dates)) return null;
  return { start: `${dates.start}T00:00:00Z`, end: `${dates.end}T23:59:59Z` };
}

function sensorLabel(code: string): string {
  return code === "S1_SAR" ? "Sentinel-1 SAR" : code === "S2_OPTICAL" ? "Sentinel-2 optical" : code;
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const demo = demoModeEnabled();
  const source: DataSource = demo ? "fixture" : "gateway";

  const [rail, setRail] = useState(true);
  const [trace, setTrace] = useState(false);
  // The demo opens on the pinned scenario's own query and AOI so the question
  // and the polygon agree; live starts with no AOI drawn.
  const [query, setQuery] = useState(demo ? ASSAM_SCENARIO.query : LIVE_INITIAL_QUERY);
  const [aoi, setAoi] = useState<GeoJSONPolygon | null>(demo ? ASSAM_SCENARIO.aoi : null);
  const [dates, setDates] = useState<TemporalWindow | null>(null);
  const [layers, setLayers] = useState<Record<LayerId, boolean>>(() => INITIAL_LAYERS(demo));

  // ── Run wiring ───────────────────────────────────────────────────────────────
  const run = useMissionRun(demo);
  const activity = useAgentActivity(demo, run);

  const complete = run.phase === "complete";
  const running = run.phase === "running";
  const validation = useMemo(() => validateAOI(aoi), [aoi]);
  const toggleLayer = useCallback((id: LayerId) => {
    setLayers((l) => ({ ...l, [id]: !l[id] }));
  }, []);

  const result = useMemo(
    () => (!demo && run.agentState ? toLiveResult(run.agentState) : null),
    [demo, run.agentState],
  );
  const extent = useAnalysisExtent(!demo && complete ? (result?.inference.traceId ?? null) : null);

  // When the water outline arrives, make sure it is visible.
  useEffect(() => {
    if (extent.status === "ready") setLayers((l) => ({ ...l, observation: true }));
  }, [extent.status]);

  // Run is locked until the inputs are valid, with the reason in words (audit
  // W2). Live mode requires an AOI: the agent no longer guesses a location.
  const dateProblem = demo ? null : dateRangeProblem(dates);
  const blockedReason =
    query.trim().length === 0
      ? "Enter a question."
      : !demo && aoi === null
        ? "Draw an area of interest on the map (Draw AOI or Rectangle) to run."
        : aoi !== null && !validation.valid
          ? (validation.findings.find((f) => f.severity === "error")?.message ?? "The AOI is invalid.")
          : dateProblem;

  const stages = toStages(run.stages);
  const currentStep: StepView | null =
    (run.stages.find((s) => s.state === "running") as StepView | undefined) ?? null;

  // ── Plan card (audit W10: show what was actually searched) ─────────────────
  const parameters = useMemo(() => {
    if (demo) {
      return {
        aoiName: ASSAM_SCENARIO.aoiName,
        aoiAreaSqM: validation.areaSqM,
        dateRange: complete ? "Latest pass vs permanent baseline" : null,
        sensors: complete ? ["SENTINEL-1"] : [],
        resolutionM: complete ? 10 : null,
        analysisType: complete ? "Surface-water change" : null,
        inferred: new Set(complete ? ["dateRange", "sensors", "analysisType"] : []),
      };
    }
    const searched = result?.search;
    const lastAttempt = searched?.attempts[searched.attempts.length - 1];
    const effective = lastAttempt
      ? `${lastAttempt.start.slice(0, 10)} → ${lastAttempt.end.slice(0, 10)}${searched?.widened ? " (widened)" : ""}`
      : null;
    const requested = dates?.start && dates?.end ? `${dates.start} → ${dates.end}` : null;
    const sensors = run.agentState?.selected_sensors ?? [];
    const hazard = (run.agentState?.intent as Record<string, unknown> | null | undefined)?.disaster_type;
    return {
      aoiName: aoi ? "Drawn on the map" : null,
      aoiAreaSqM: validation.areaSqM,
      dateRange: effective ?? requested,
      sensors: sensors.map(sensorLabel),
      resolutionM: result?.confidence.resolutionM ?? null,
      analysisType: typeof hazard === "string" ? `Surface water · ${hazard}` : null,
      inferred: new Set(effective && !requested ? ["dateRange"] : []),
    };
  }, [demo, complete, aoi, validation.areaSqM, dates, run.agentState, result]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleRun = () => {
    if (running || blockedReason) return;
    run.start(query, aoi, toWindow(dates));
  };

  const handleReset = () => {
    run.reset();
    setQuery(demo ? ASSAM_SCENARIO.query : LIVE_INITIAL_QUERY);
    setAoi(demo ? ASSAM_SCENARIO.aoi : null);
    setDates(null);
  };

  const runId = run.traceId ?? run.jobId ?? "—";
  const closeTrace = useCallback(() => setTrace(false), []);

  // ── Rail status card: idle / running / result / failure (audit F2, F3) ─────
  let statusCard: React.ReactNode = null;
  if (demo) {
    statusCard = complete ? (
      <section className="sqd-card sqd-result" aria-label="Result">
        <header className="sqd-card-head">
          <span className="sqd-eyebrow">Result</span>
          <ProvenanceBadge source="fixture" at={FIXTURE_EPOCH} />
        </header>
        <div className="sqd-figure">
          <b>{ASSAM_SCENARIO.change.areaSqKm.toFixed(2)}</b>
          <span>km² of new water</span>
        </div>
        <p className="sqd-figure-sub">
          Pinned demo scene. The change, confidence and evidence are in the intelligence panel
          under the map.
        </p>
      </section>
    ) : running ? (
      <RunningCard current={currentStep} />
    ) : null;
  } else if (running) {
    statusCard = <RunningCard current={currentStep} />;
  } else if (complete && result) {
    statusCard = <ResultCard result={result} extent={extent} onTrace={() => setTrace(true)} />;
  } else if (run.phase === "failed" && run.failureKind) {
    statusCard = (
      <FailureCard
        kind={run.failureKind}
        message={result?.failure?.text ?? run.error?.message ?? "The run failed."}
        reason={result?.failure?.reason ?? (run.failureKind === "agent" ? (run.error?.code ?? null) : null)}
        hint={result?.failure?.hint ?? failureHint(null)}
        traceId={run.error?.trace_id ?? run.traceId}
        onRetry={handleRun}
        onTrace={() => setTrace(true)}
      />
    );
  } else {
    statusCard = <IdleCard aoiReady={aoi !== null && validation.valid} />;
  }

  return (
    <>
      <DashboardTopBar activeHref={ROUTES.console} signedIn={run.session?.kind === "ready"} />
      <div className="app-shell app-shell--flat">
        <main className="main sqd" id="mission-main" tabIndex={-1}>
          <div className={`sqd-stage ${rail ? "" : "is-rail-hidden"}`}>
            {rail ? (
              <aside className="sqd-rail" aria-label="Mission">
                <div className="sqd-rail-head">
                  <h1 className="sqd-title">Mission overview</h1>
                  {demo ? <ProvenanceBadge source="fixture" at={FIXTURE_EPOCH} /> : null}
                </div>
                <ErrorBoundary area="Mission panel">
                  <QueryConsole
                    value={query}
                    onChange={setQuery}
                    onRun={handleRun}
                    running={running}
                    onReset={handleReset}
                    blockedReason={blockedReason}
                    window={dates}
                    onWindowChange={setDates}
                    showDates={!demo}
                  />
                  {statusCard}
                  <StageList stages={stages} />
                  <PlanParameters parameters={parameters} aoiValidation={validation} />
                  {demo && complete ? (
                    <ReportCard missionId={ASSAM_SCENARIO.missionId} />
                  ) : null}
                </ErrorBoundary>
              </aside>
            ) : null}

            <section className="sqd-map" aria-label="Map">
              <ErrorBoundary area="Map">
                <MapCanvas
                  complete={complete}
                  aoi={aoi}
                  onAoiChange={setAoi}
                  visible={layers}
                  onToggleLayer={toggleLayer}
                  extent={extent.status === "ready" ? extent.data : null}
                  aoiLocked={running}
                />
              </ErrorBoundary>
              <button
                className="sqd-rail-toggle"
                onClick={() => setRail(!rail)}
                aria-label={rail ? "Hide mission rail" : "Show mission rail"}
                title={rail ? "Hide mission rail" : "Show mission rail"}
                type="button"
              >
                {rail ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />}
              </button>
            </section>
          </div>

          {/* Detail under the map. Demo reads the pinned scenario; live reads
              only what the agent published. */}
          <section className="sqd-below intel-section" aria-label="Intelligence">
            <ErrorBoundary area="Intelligence panel">
              {demo ? (
                <IntelligencePanel
                  scenario={complete ? ASSAM_SCENARIO : null}
                  source={source}
                  sourceAt={FIXTURE_EPOCH}
                  revealed={complete}
                  aoiAreaSqM={validation.areaSqM}
                />
              ) : complete && result ? (
                <LiveIntelligence result={result} />
              ) : null}
            </ErrorBoundary>
          </section>

          <PageTelemetry run={run} />

          <footer className="app-footer">
            <div>
              <Globe2 size={14} />
              <b>SatQuery AI</b>
              <span>Evidence-first satellite intelligence</span>
            </div>
            <div>
              <span>Sentinel-1 via Microsoft Planetary Computer</span>
              <span>•</span>
              <span>Basemap © Esri</span>
            </div>
          </footer>
        </main>

        <BeginnerGuide demo={demo} />

        {/* Agent activity toasts float bottom-right over everything (P5 §2C). */}
        <AgentActivityToasts events={activity.events} onDismiss={activity.dismiss} />

        {trace && (
          <TraceDrawer
            stages={stages}
            runId={runId}
            ids={{
              "trace id": run.traceId,
              "job id": run.jobId,
              "mission id": run.missionId,
              "inference trace": result?.inference.traceId ?? null,
            }}
            exportPayload={demo ? null : (run.agentState ?? null)}
            onClose={closeTrace}
          />
        )}
      </div>
    </>
  );
}
