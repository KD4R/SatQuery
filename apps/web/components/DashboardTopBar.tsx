"use client";

/**
 * The console's telemetry bar, retabbed for the dashboard's own sections:
 * Mission / Monitoring / Admin. Same chrome as the console (mission breadcrumb,
 * env chip, gateway chip, UTC clock) so the two surfaces read as one product.
 *
 * The gateway chip is a real health check, never an assumption. In demo mode
 * the clock freezes and ENV reads DEMO, same as the console. Pass `run` on
 * pages that own a run (the mission dashboard); pages without one report
 * honestly that they have nothing in flight.
 */

import { useEffect, useState } from "react";

import { getHealth } from "../lib/api/client";
import { demoModeEnabled } from "../lib/api/source";
import type { MissionRun } from "../lib/useMissionRun";
import { TopTelemetryBar, type SystemState } from "./shell/TopTelemetryBar";

const DASHBOARD_TABS = [
  { label: "Mission", href: "/dashboard" },
  { label: "Monitoring", href: "/dashboard/monitoring" },
  { label: "Admin", href: "/dashboard/admin" },
];

export default function DashboardTopBar({
  run = null,
  activeHref,
}: {
  /** A run in flight on this page, if the page owns one. */
  run?: Pick<MissionRun, "phase" | "jobId" | "agentState"> | null;
  activeHref: string;
}) {
  const [gatewayUp, setGatewayUp] = useState<boolean | null>(null);
  const demo = demoModeEnabled();

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

  const state: SystemState =
    run?.phase === "running"
      ? "processing"
      : run?.phase === "failed"
        ? "degraded"
        : run?.phase === "complete"
          ? "active"
          : "idle";

  return (
    <TopTelemetryBar
      missionId={run?.agentState?.mission_id ?? run?.jobId ?? null}
      runId={run?.jobId ?? null}
      state={state}
      source={demo ? "fixture" : "gateway"}
      frozenClock={demo ? "05:42:00" : undefined}
      gatewayReachable={gatewayUp}
      tabs={DASHBOARD_TABS}
      activeHref={activeHref}
    />
  );
}
