"use client";

/**
 * The dashboard family's single nav bar — replaces the old two-bar stack
 * (brand/telemetry bar + MISSION CONTROL header).
 *
 * Layout: SATQUERY brand · jelly section chips · icon actions.
 * Sections are the five product areas (Mission absorbs the map workspace);
 * everything else the old UI spread across bars is an icon action:
 * history, alerts, settings, theme, search, profile.
 *
 * The UTC clock / gateway / state telemetry lives at the bottom of the page
 * (PageTelemetry), not in this bar.
 *
 * The gateway state is a real health check, never an assumption. In demo mode
 * the clock freezes and ENV reads DEMO. Pass `run` on pages that own a run.
 */

import { useEffect, useState } from "react";
import {
  Bell,
  FileText,
  Globe2,
  History,
  Search,
  Settings,
  ShieldCheck,
  Activity,
  Moon,
  Sun,
  type LucideIcon,
} from "lucide-react";

import { demoModeEnabled } from "../lib/api/source";
import JellyNav from "./JellyNav";
import { applyTheme, readTheme, type Theme } from "../lib/theme";

export interface DashboardTab {
  label: string;
  href: string;
  icon?: LucideIcon;
}

/** The five product sections. Mission absorbs the map workspace. */
export const DASHBOARD_TABS: DashboardTab[] = [
  { label: "Mission", href: "/dashboard", icon: Globe2 },
  { label: "Monitoring", href: "/dashboard/monitoring", icon: Activity },
  { label: "Evidence", href: "/dashboard/evidence", icon: ShieldCheck },
  { label: "Reports", href: "/dashboard/reports", icon: FileText },
  { label: "Admin", href: "/dashboard/admin", icon: ShieldCheck },
];

export default function DashboardTopBar({
  activeHref,
}: {
  activeHref: string;
}) {
  const demo = demoModeEnabled();
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => setTheme(readTheme()), []);

  return (
    <header className="dash-navbar">
      <span className="dash-brand heading">SATQUERY</span>

      <JellyNav tabs={DASHBOARD_TABS} activeHref={activeHref} />

      <div className="band-spacer" />

      <div className="dash-nav-actions">
        <a className="icon-btn" href="/dashboard/history" aria-label="History" title="History">
          <History size={16} />
        </a>
        <a className="icon-btn" href="/dashboard/alerts" aria-label="Alerts and notifications" title="Alerts">
          <Bell size={16} />
        </a>
        <a className="icon-btn" href="/dashboard/settings" aria-label="Settings" title="Settings">
          <Settings size={16} />
        </a>
        <button
          className="icon-btn"
          aria-label="Toggle theme"
          onClick={() => {
            const next: Theme = theme === "dark" ? "light" : "dark";
            applyTheme(next);
            setTheme(next);
          }}
        >
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        <button className="icon-btn" aria-label="Search">
          <Search size={16} />
        </button>
        <div className="avatar" title={demo ? "Demo session" : "Signed in"}>
          SQ
        </div>
      </div>
    </header>
  );
}
