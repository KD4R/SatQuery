"use client";

/**
 * The console (P5-01 … P5-13).
 *
 * Composes the shell, the map and the two rails, and owns the one piece of state
 * they share: which run is happening and what it produced.
 *
 * Demo and live are chosen once, here, from NEXT_PUBLIC_DEMO_MODE, and the choice
 * is visible in the telemetry bar as ENV: DEMO or ENV: LIVE. In demo the scenario
 * comes from lib/fixtures and every panel carries the fixture badge. In live the
 * panels stay empty until the backend supplies something, because the fixture is
 * never used as a fallback for a failed call.
 */

import dynamic from "next/dynamic";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../lib/fixtures";
import { buildTimeMachine } from "../lib/map/timeLayers";
import { DEMO_AGENT_EVENTS, demoEventAt } from "../lib/fixtures";
import { useMissionEvents } from "../lib/ws/useMissionEvents";
import { hasAccessToken } from "../lib/api/gateway";
import { demoModeEnabled, type DataSource } from "../lib/api/source";
import { getHealth } from "../lib/api/client";
import { useMissionRun } from "../lib/useMissionRun";
import { validateAOI } from "../lib/geo/validate";
import type { GeoJSONPolygon } from "../lib/api/types";
import type { LayerId } from "./map/MapWorkspace";

import { MissionShell } from "./shell/MissionShell";
import { TopTelemetryBar, type SystemState } from "./shell/TopTelemetryBar";
import { MissionQueryPanel } from "./console/MissionQueryPanel";
import { MissionTimeline } from "./console/MissionTimeline";
import { AgentActivityToasts } from "./console/AgentActivityToasts";
import { IntelligencePanel } from "./evidence/IntelligencePanel";
import { ErrorBoundary, ErrorState } from "./system/ErrorBoundary";
import { Label, StatusChip } from "./system/primitives";

/**
 * MapLibre is ~800 KB of WebGL. Loading it on demand keeps it out of the first
 * paint and off the critical path (P5-16). ssr:false because it needs a canvas.
 */
const MapWorkspace = dynamic(
  () => import("./map/MapWorkspace").then((m) => m.MapWorkspace),
  {
    ssr: false,
    loading: () => (
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center" }}>
        <span className="label label-faint">Loading map…</span>
      </div>
    ),
  },
);

const ALL_LAYERS: Record<LayerId, boolean> = {
  observation: true,
  // The demo's Time Machine epochs fall under this category; the rail needs it
  // on to show "Before". Live mode keeps it off until the operator asks.
  baseline: demoModeEnabled(),
  change: true,
  confidence: false,
  aoi: true,
};

export default function MissionConsole() {
  const demo = demoModeEnabled();
  const source: DataSource = demo ? "fixture" : "gateway";

  const [query, setQuery] = useState(demo ? ASSAM_SCENARIO.query : "");
  const [aoi, setAoi] = useState<GeoJSONPolygon | null>(
    demo ? ASSAM_SCENARIO.aoi : null,
  );
  const [layers, setLayers] = useState<Record<LayerId, boolean>>(ALL_LAYERS);
  const [gatewayUp, setGatewayUp] = useState<boolean | null>(null);

  const run = useMissionRun(demo);

  /* ── Live agent events (P5 §2C) ───────────────────────────────────────────
     Demo feeds the rail from pinned fixtures on the same schedule as the run
     script — no socket, deterministic for Playwright. Live opens the gateway
     mission socket (only when a token exists; the socket is useless without
     one) and receives what the orchestrator actually emitted. */
  const [demoEventTick, setDemoEventTick] = useState(0);
  const [demoDismissed, setDemoDismissed] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    if (!demo || run.phase !== "running") return;
    setDemoEventTick(0); // a re-run replays the feed from the top
    setDemoDismissed(new Set());
    const timers: ReturnType<typeof setTimeout>[] = [];
    DEMO_AGENT_EVENTS.forEach((e, i) => {
      timers.push(setTimeout(() => setDemoEventTick(i + 1), e.atMs));
    });
    return () => timers.forEach(clearTimeout);
  }, [demo, run.phase]);

  const demoEvents = useMemo(
    () =>
      DEMO_AGENT_EVENTS.slice(0, demoEventTick)
        .map(demoEventAt)
        .filter((e) => !demoDismissed.has(e.id)),
    [demoEventTick, demoDismissed],
  );

  const live = useMissionEvents(
    demo ? null : (run.jobId ?? null),
    !demo && run.phase === "running" && hasAccessToken(),
  );
  const agentEvents = demo ? demoEvents : live.events;
  const dismissEvent = demo
    ? (id: string) => setDemoDismissed((prev) => new Set(prev).add(id))
    : live.dismiss;
  useEffect(() => {
    let live = true;
    const controller = new AbortController();
    getHealth(controller.signal)
      .then(() => live && setGatewayUp(true))
      .catch(() => live && setGatewayUp(false));
    return () => {
      live = false;
      controller.abort();
    };
  }, []);

  const validation = useMemo(() => validateAOI(aoi), [aoi]);

  const toggleLayer = useCallback((id: LayerId) => {
    setLayers((l) => ({ ...l, [id]: !l[id] }));
  }, []);

  // Only the pre-run backdrop lives here now: once a run completes the Time
  // Machine owns the baseline/observed/change rasters as crossfade epochs, so
  // listing them as static overlays too would draw every scene twice.
  const overlays = useMemo(() => {
    if (!demo) return [];
    const s = ASSAM_SCENARIO.overlays;
    return [{ id: "s1-vv", url: s["s1-vv"]!.url, bbox: s["s1-vv"]!.bbox }];
  }, [demo]);

  const complete = run.phase === "complete";

  // PRD §2A: the scrub rail appears with the run's result, built from the same
  // scenario — one source of truth for the map's temporal states.
  const timeMachine = useMemo(
    () => (demo && complete ? buildTimeMachine(ASSAM_SCENARIO) : null),
    [demo, complete],
  );
  const scenario = demo && complete ? ASSAM_SCENARIO : null;

  const systemState: SystemState =
    run.phase === "running"
      ? "processing"
      : run.phase === "failed"
        ? "degraded"
        : run.phase === "complete"
          ? "active"
          : "idle";

  const parameters = useMemo(
    () => ({
      aoiName: demo ? ASSAM_SCENARIO.aoiName : aoi ? "Operator-drawn AOI" : null,
      aoiAreaSqM: validation.areaSqM,
      dateRange: complete && demo ? "Latest pass vs permanent baseline" : null,
      sensors: complete && demo ? ["SENTINEL-1"] : [],
      resolutionM: complete && demo ? 10 : null,
      analysisType: complete && demo ? "Surface-water change" : null,
      inferred: new Set(
        complete && demo ? ["dateRange", "sensors", "analysisType"] : [],
      ),
    }),
    [demo, aoi, validation.areaSqM, complete],
  );

  return (
    <div style={{ position: "relative", height: "100%" }}>
    <MissionShell
      telemetry={
        <TopTelemetryBar
          missionId={complete || run.phase === "running" ? ASSAM_SCENARIO.missionId : null}
          runId={run.jobId}
          state={systemState}
          source={source}
          frozenClock={demo ? "05:42:00" : undefined}
          gatewayReachable={gatewayUp}
        />
      }
      queryRail={
        <ErrorBoundary area="Mission panel">
          <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <div style={{ flex: "0 0 auto" }}>
              <MissionQueryPanel
                query={query}
                onQueryChange={setQuery}
                onRun={() => run.start(query, aoi)}
                running={run.phase === "running"}
                parameters={parameters}
                aoiValidation={validation}
                blockedReason={null}
              />
            </div>
            <div
              style={{
                flex: "1 1 auto",
                minHeight: 0,
                borderTop: "1px solid var(--hairline)",
              }}
            >
              {run.phase === "failed" && run.error ? (
                <div style={{ padding: 10 }}>
                  <ErrorState
                    title="Inference unavailable"
                    error={run.error}
                    runId={run.jobId}
                    onRetry={() => run.start(query, aoi)}
                  />
                </div>
              ) : run.stages.length > 0 ? (
                <MissionTimeline stages={run.stages} />
              ) : (
                <div style={{ padding: 20, textAlign: "center" }}>
                  <span className="label label-faint">Timeline appears on run</span>
                </div>
              )}
            </div>
          </div>
        </ErrorBoundary>
      }
      map={
        <ErrorBoundary area="Map">
          <MapWorkspace
            center={[93.8962, 26.7914]}
            zoom={12.4}
            aoi={aoi}
            onAoiChange={setAoi}
            overlays={overlays}
            changeGeoJsonUrl={
              complete && demo ? ASSAM_SCENARIO.changeGeoJsonUrl : null
            }
            timeMachine={timeMachine}
            visible={layers}
            onToggleLayer={toggleLayer}
          />
        </ErrorBoundary>
      }
      intelRail={
        <ErrorBoundary area="Intelligence panel">
          <IntelligencePanel
            scenario={scenario}
            source={source}
            sourceAt={FIXTURE_EPOCH}
            revealed={complete}
          />
        </ErrorBoundary>
      }
      statusLeft={
        <div className="row" style={{ gap: 12 }}>
          <Label faint>
            {run.phase === "running"
              ? "Analysis in progress"
              : run.phase === "complete"
                ? "Analysis complete"
                : run.phase === "failed"
                  ? "Analysis failed"
                  : "Idle"}
          </Label>
          {demo ? (
            <StatusChip
              tone="fixture"
              title="Every value on screen comes from a pinned fixture, not the backend."
            >
              Demo fixtures
            </StatusChip>
          ) : null}
        </div>
      }
      statusRight={
        <div className="row" style={{ gap: 12 }}>
          {complete ? (
            <Link
              href={`/missions/${ASSAM_SCENARIO.missionId}/report`}
              className="label"
              style={{ color: "var(--signal)" }}
            >
              REPORT →
            </Link>
          ) : null}
          <Link href="/missions" className="label" style={{ color: "var(--ink-faint)" }}>
            MISSIONS
          </Link>
          <Link href="/monitoring" className="label" style={{ color: "var(--ink-faint)" }}>
            MONITORING
          </Link>
          <Label faint>EPSG:4326</Label>
          <Label faint>
            {gatewayUp === null
              ? "Gateway: checking"
              : gatewayUp
                ? "Gateway: reachable"
                : "Gateway: unreachable"}
          </Label>
        </div>
      }
      />
      {/* Agent activity toasts float bottom-right over everything (P5 §2C). */}
      <AgentActivityToasts events={agentEvents} onDismiss={dismissEvent} />
    </div>
  );
}
