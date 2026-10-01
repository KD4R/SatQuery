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
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Globe2, PanelLeftClose, PanelLeftOpen } from "lucide-react";

import PageTelemetry from "./PageTelemetry";
import MapCanvas from "./MapCanvas";
import QueryConsole from "./QueryConsole";
import PlanParameters from "./PlanParameters";
import StageList from "./StageList";
import ReportCard from "./ReportCard";
import TraceDrawer from "./TraceDrawer";
import DashboardTopBar from "./DashboardTopBar";
import { AgentActivityToasts } from "./console/AgentActivityToasts";
import { ErrorBoundary } from "./system/ErrorBoundary";
import { ProvenanceBadge } from "./system/primitives";
import { FailureCard, IdleCard, LiveIntelligence, ResultCard, RunningCard } from "./dash/LivePanels";
import { FlowNav, type FlowStep } from "./dash/FlowNav";
import { WherePanel, type WherePanelHandle } from "./dash/WherePanel";
import { WhenPanel, type WhenPanelHandle } from "./dash/WhenPanel";
import type { LayerId } from "./map/MapWorkspace";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../lib/fixtures";
import { useMissionRun } from "../lib/useMissionRun";
import { useAgentActivity } from "../lib/useAgentActivity";
import { demoModeEnabled, type DataSource } from "../lib/api/source";
import { validateAOI } from "../lib/geo/validate";
import { failureHint, toLiveResult } from "../lib/live/result";
import { useAnalysisExtent } from "../lib/live/useAnalysisExtent";
import { dateRangeProblem, describeRange, toTemporalWindow } from "../lib/live/dates";
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

/**
 * Bring a rail section into view. Scrolls the rail itself (not the page), so
 * the top bar and the map stay where they are; below the map (narrow screens,
 * or the intelligence section) falls back to scrolling the page.
 */
function scrollToId(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  const rail = el.closest<HTMLElement>(".sqd-rail");
  if (rail && rail.scrollHeight > rail.clientHeight) {
    const flow = rail.querySelector<HTMLElement>(".sqd-flow");
    const top = el.getBoundingClientRect().top - rail.getBoundingClientRect().top + rail.scrollTop;
    rail.scrollTo({ top: Math.max(0, top - (flow?.offsetHeight ?? 0) - 8), behavior: "smooth" });
    return;
  }
  el.scrollIntoView({ behavior: "smooth", block: "start" });
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
  const [aoiLabel, setAoiLabel] = useState<string | null>(demo ? ASSAM_SCENARIO.aoiName : null);
  const [dates, setDates] = useState<TemporalWindow | null>(null);
  const [focus, setFocus] = useState<{ bbox: [number, number, number, number]; nonce: number } | null>(null);
  const [drawRequest, setDrawRequest] = useState<{ mode: "rectangle" | "polygon"; nonce: number } | null>(null);
  const whereRef = useRef<WherePanelHandle | null>(null);
  const whenRef = useRef<WhenPanelHandle | null>(null);
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

  // Bring the answer (or the reason it failed) into view when the run ends.
  useEffect(() => {
    if (run.phase === "complete" || run.phase === "failed") scrollToId("step-result");
  }, [run.phase]);

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
        ? "Set an area in step 1: search a place, or draw a rectangle or polygon on the map."
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
    const requested = dates && !dateRangeProblem(dates) ? describeRange(dates) : null;
    const sensors = run.agentState?.selected_sensors ?? [];
    const hazard = (run.agentState?.intent as Record<string, unknown> | null | undefined)?.disaster_type;
    return {
      aoiName: aoi ? (aoiLabel ?? "Drawn on the map") : null,
      aoiAreaSqM: validation.areaSqM,
      dateRange: effective ?? requested,
      sensors: sensors.map(sensorLabel),
      resolutionM: result?.confidence.resolutionM ?? null,
      analysisType: typeof hazard === "string" ? `Surface water · ${hazard}` : null,
      inferred: new Set(effective && !requested ? ["dateRange"] : []),
    };
  }, [demo, complete, aoi, aoiLabel, validation.areaSqM, dates, run.agentState, result]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const handleRun = () => {
    if (running || blockedReason) return;
    run.start(query, aoi, toTemporalWindow(dates));
  };

  const handleReset = () => {
    run.reset();
    setQuery(demo ? ASSAM_SCENARIO.query : LIVE_INITIAL_QUERY);
    setAoi(demo ? ASSAM_SCENARIO.aoi : null);
    setAoiLabel(demo ? ASSAM_SCENARIO.aoiName : null);
    setDates(null);
  };

  const setAoiFromMap = useCallback((next: GeoJSONPolygon | null) => {
    setAoi(next);
    setAoiLabel(next ? "Drawn on the map" : null);
  }, []);

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

  // ── Flow navigation (replaces the floating guide) ──────────────────────────
  const whereDone = aoi !== null && validation.valid;
  const whenProblem = dateRangeProblem(dates);
  const askDone = query.trim().length > 0;
  const flow: FlowStep[] = [
    {
      key: "where",
      label: "Where",
      hint: whereDone ? (aoiLabel ?? "Area set") : aoi ? "Area invalid" : "Search a place, set the area",
      state: whereDone ? "done" : aoi ? "error" : "todo",
      onGo: () => {
        scrollToId("step-where");
        whereRef.current?.focusSearch();
      },
    },
    {
      key: "when",
      label: "When",
      hint: whenProblem ? "Check the dates" : dates ? describeRange(dates).split(" · ")[0]! : "Auto (last 90 days)",
      state: whenProblem ? "error" : dates ? "done" : "optional",
      onGo: () => {
        scrollToId("step-when");
        whenRef.current?.focusDates();
      },
    },
    {
      key: "ask",
      label: "Ask",
      hint: askDone ? "Question ready" : "Type your question",
      state: askDone ? "done" : "todo",
      onGo: () => {
        scrollToId("step-ask");
        document.getElementById("mission-query")?.focus();
      },
    },
    {
      key: "run",
      label: "Run",
      hint: running ? "Working…" : complete ? "Finished" : run.phase === "failed" ? "Failed" : blockedReason ? "Waiting on the steps above" : "Ready to run",
      state: running ? "running" : complete ? "done" : run.phase === "failed" ? "error" : blockedReason ? "todo" : "current",
      onGo: () => {
        if (!running && !blockedReason) handleRun();
        else if (blockedReason) flow.find((f) => f.state === "todo" || f.state === "error")?.onGo();
        else scrollToId("step-ask");
      },
    },
    {
      key: "result",
      label: "Result",
      hint: complete
        ? demo
          ? `${ASSAM_SCENARIO.change.areaSqKm.toFixed(2)} km² (demo)`
          : result?.areaKm2 != null
            ? `${result.areaKm2.toFixed(2)} km² water`
            : "Ready"
        : run.phase === "failed"
          ? "See why it failed"
          : "Appears after the run",
      state: complete ? "done" : run.phase === "failed" ? "error" : "todo",
      disabled: !(complete || run.phase === "failed"),
      onGo: () => scrollToId("step-result"),
    },
  ];
  // The first step still needing input is the current one.
  const firstOpen = flow.findIndex((f) => f.state === "todo" || f.state === "error");
  if (firstOpen !== -1 && flow[firstOpen]!.state === "todo" && flow[firstOpen]!.key !== "result") {
    flow[firstOpen] = { ...flow[firstOpen]!, state: "current" };
  }

  return (
    <>
      <DashboardTopBar activeHref={ROUTES.console} signedIn={run.session?.kind === "ready"} />
      <div className="app-shell app-shell--flat">
        <main className="main sqd" id="mission-main" tabIndex={-1}>
          <div className={`sqd-stage ${rail ? "" : "is-rail-hidden"}`}>
            {rail ? (
              <aside className="sqd-rail" aria-label="Mission">
                <FlowNav steps={flow} />
                <div className="sqd-rail-head">
                  <h1 className="sqd-title">Mission overview</h1>
                  {demo ? <ProvenanceBadge source="fixture" at={FIXTURE_EPOCH} /> : null}
                </div>
                <ErrorBoundary area="Mission panel">
                  <WherePanel
                    ref={whereRef}
                    demo={demo}
                    aoi={aoi}
                    aoiLabel={aoiLabel}
                    validation={validation}
                    locked={running}
                    onFlyTo={(bbox) => setFocus({ bbox, nonce: Date.now() })}
                    onSetAoi={(next, label) => {
                      setAoi(next);
                      setAoiLabel(label);
                    }}
                    onDraw={(mode) => setDrawRequest({ mode, nonce: Date.now() })}
                  />
                  <WhenPanel ref={whenRef} demo={demo} value={dates} onChange={setDates} locked={running} />
                  <QueryConsole
                    value={query}
                    onChange={setQuery}
                    onRun={handleRun}
                    running={running}
                    onReset={handleReset}
                    blockedReason={blockedReason}
                  />
                  <div id="step-result">{statusCard}</div>
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
                  onAoiChange={setAoiFromMap}
                  visible={layers}
                  onToggleLayer={toggleLayer}
                  extent={extent.status === "ready" ? extent.data : null}
                  aoiLocked={running}
                  focusBounds={focus}
                  drawRequest={drawRequest}
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
