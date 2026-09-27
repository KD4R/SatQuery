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
import {
  Activity,
  Bell,
  FileText,
  Globe2,
  History,
  ShieldCheck,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";

import { getHealth } from "../lib/api/client";
import { demoModeEnabled } from "../lib/api/source";
import type { MissionRun } from "../lib/useMissionRun";
import { TopTelemetryBar, type SystemState } from "./shell/TopTelemetryBar";
import JellyNav from "./JellyNav";

export interface DashboardTab {
  label: string;
  href: string;
  icon?: LucideIcon;
}

/** The section tabs with their lucide icons resolved — used by the nav views. */
export function DashboardTopBarTabs(tabs: DashboardTab[]) {
  return tabs;
}

/** The old sidebar's items, promoted to the top nav. Order = workspace order. */
const DASHBOARD_TABS: DashboardTab[] = [
  { label: "Mission", href: "/dashboard", icon: Globe2 },
  { label: "Map", href: "/dashboard/map", icon: Globe2 },
  { label: "Monitoring", href: "/dashboard/monitoring", icon: Activity },
  { label: "Evidence", href: "/dashboard/evidence", icon: ShieldCheck },
  { label: "History", href: "/dashboard/history", icon: History },
  { label: "Reports", href: "/dashboard/reports", icon: FileText },
  { label: "Alerts", href: "/dashboard/alerts", icon: Bell },
  { label: "Settings", href: "/dashboard/settings", icon: SlidersHorizontal },
  { label: "Admin", href: "/dashboard/admin", icon: ShieldCheck },
  { label: "Preview", href: "/dashboard/preview" },
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
      withIcons
      navSlot={<JellyNav tabs={DASHBOARD_TABS} />}
    />
  );
}
