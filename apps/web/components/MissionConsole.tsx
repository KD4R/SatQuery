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
import { useCallback, useEffect, useMemo, useState } from "react";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../lib/fixtures";
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
  baseline: false,
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

  /* Health check. Its only job is the reachability chip; a failure here never
     blocks the console or changes what any panel claims. */
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

  const overlays = useMemo(() => {
    if (!demo) return [];
    const s = ASSAM_SCENARIO.overlays;
    return [
      { id: "s1-vv", url: s["s1-vv"]!.url, bbox: s["s1-vv"]!.bbox },
      { id: "baseline", url: s.baseline!.url, bbox: s.baseline!.bbox, opacity: 1 },
      { id: "observed", url: s.observed!.url, bbox: s.observed!.bbox },
    ];
  }, [demo]);

  const complete = run.phase === "complete";
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
            overlays={complete ? overlays : overlays.slice(0, 1)}
            changeGeoJsonUrl={
              complete && demo ? ASSAM_SCENARIO.changeGeoJsonUrl : null
            }
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
  );
}
