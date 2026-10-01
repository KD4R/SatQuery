"use client";

/**
 * The dashboard family's single nav bar — replaces the old two-bar stack
 * (brand/telemetry bar + MISSION CONTROL header).
 *
 * Layout: SATQUERY brand · jelly section chips · icon actions.
 * Sections are the five product areas (Mission absorbs the map workspace);
 * everything else the old UI spread across bars is an icon action:
 * history, alerts, settings, theme, profile.
 *
 * The UTC clock / gateway / state telemetry lives at the bottom of the page
 * (PageTelemetry), not in this bar.
 *
 * The gateway state is a real health check, never an assumption. In demo mode
 * the clock freezes and ENV reads DEMO. Pass `run` on pages that own a run.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bell,
  FileText,
  Globe2,
  History,
  Settings,
  ShieldCheck,
  Activity,
  Moon,
  Sun,
  type LucideIcon,
} from "lucide-react";

import { demoModeEnabled } from "../lib/api/source";
import { hasAccessToken } from "../lib/api/gateway";
import JellyNav from "./JellyNav";
import { ROUTES } from "../lib/nav";
import { applyTheme, readTheme, type Theme } from "../lib/theme";

export interface DashboardTab {
  label: string;
  href: string;
  icon?: LucideIcon;
}

/** The five product sections. Mission absorbs the map workspace. */
export const DASHBOARD_TABS: DashboardTab[] = [
  { label: "Mission", href: ROUTES.console, icon: Globe2 },
  { label: "Monitoring", href: ROUTES.monitoring, icon: Activity },
  { label: "Evidence", href: ROUTES.evidence, icon: ShieldCheck },
  { label: "Reports", href: ROUTES.reports, icon: FileText },
  { label: "Admin", href: ROUTES.admin, icon: ShieldCheck },
];

export default function DashboardTopBar({
  activeHref,
  signedIn,
}: {
  activeHref: string;
  /** Live session state from the page that owns it; read once on mount otherwise. */
  signedIn?: boolean;
}) {
  const demo = demoModeEnabled();
  const [theme, setTheme] = useState<Theme>("dark");
  const [tokenPresent, setTokenPresent] = useState(false);

  useEffect(() => setTheme(readTheme()), []);
  useEffect(() => setTokenPresent(hasAccessToken()), []);
  const isSignedIn = signedIn ?? tokenPresent;

  return (
    <header className="dash-navbar">
      <Link className="dash-brand heading" href={ROUTES.home} aria-label="SatQuery home">
        SATQUERY
      </Link>

      <JellyNav tabs={DASHBOARD_TABS} activeHref={activeHref} />

      <div className="band-spacer" />

      <div className="dash-nav-actions">
        <Link className="icon-btn" href={ROUTES.history} aria-label="History" title="History">
          <History size={16} />
        </Link>
        <Link className="icon-btn" href={ROUTES.alerts} aria-label="Alerts and notifications" title="Alerts">
          <Bell size={16} />
        </Link>
        <Link className="icon-btn" href={ROUTES.settings} aria-label="Settings" title="Settings">
          <Settings size={16} />
        </Link>
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
        <div
          className={`avatar ${!demo && !isSignedIn ? "is-signed-out" : ""}`}
          title={demo ? "Demo session" : isSignedIn ? "Signed in (token held in memory)" : "Not signed in"}
          aria-label={demo ? "Demo session" : isSignedIn ? "Signed in" : "Not signed in"}
          role="img"
        >
          SQ
        </div>
      </div>
    </header>
  );
}
