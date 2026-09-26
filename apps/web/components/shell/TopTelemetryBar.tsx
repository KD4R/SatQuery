"use client";

/**
 * The two hairline bands at the top of the console (P5-01, P5-04).
 *
 * Row one carries identity and system state; row two carries the mission telemetry
 * an operator needs at a glance without opening a panel — mission id, run id, UTC
 * clock, environment. Dense at the edges, empty in the middle, which is what leaves
 * the map room to be the subject.
 *
 * The clock is the only thing in the console that ticks. It is suppressed in demo
 * mode so the screen is byte-identical on every run (P5-17).
 */

import { useEffect, useState } from "react";

import { Label, StatusChip } from "../system/primitives";
import type { DataSource } from "../../lib/api/source";

const NAV_TABS = [
  { label: "Mission", href: "/console" },
  { label: "Monitoring", href: "/monitoring" },
  { label: "Archive", href: "/missions" },
];

export type SystemState = "active" | "idle" | "processing" | "degraded" | "offline";

const STATE_TONE = {
  active: "active",
  processing: "active",
  idle: "idle",
  degraded: "warn",
  offline: "warn",
} as const;

function utcClock(d: Date): string {
  const p = (n: number) => n.toString().padStart(2, "0");
  return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`;
}

export interface TopTelemetryBarProps {
  missionId: string | null;
  runId: string | null;
  state: SystemState;
  source: DataSource;
  /** Fixed clock for the deterministic demo and for tests. */
  frozenClock?: string;
  gatewayReachable: boolean | null;
}

export function TopTelemetryBar({
  missionId,
  runId,
  state,
  source,
  frozenClock,
  gatewayReachable,
}: TopTelemetryBarProps) {
  const [clock, setClock] = useState<string>(frozenClock ?? "--:--:--");

  useEffect(() => {
    if (frozenClock) return;
    // Rendering the clock only after mount avoids a server/client text mismatch.
    const tick = () => setClock(utcClock(new Date()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [frozenClock]);

  return (
    <header>
      {/* Row 0 — brand, tab nav, clock/state (reference chrome) */}
      <div className="console-nav">
        <div className="row" style={{ gap: 10 }}>
          <span
            aria-hidden="true"
            style={{
              width: 14,
              height: 14,
              outline: "1px solid rgba(80, 200, 120, 0.65)",
              display: "inline-block",
            }}
          />
          <span
            className="heading"
            style={{ fontSize: 13, letterSpacing: "0.28em", fontWeight: 700 }}
          >
            SATQUERY
          </span>
        </div>

        <nav className="console-nav-tabs" aria-label="Console sections">
          {NAV_TABS.map((t) => (
            <a
              key={t.label}
              href={t.href}
              className={`console-nav-tab${
                t.label === "Mission" ? " console-nav-tab-active" : ""
              }`}
            >
              {t.label}
            </a>
          ))
          }
        </nav>

        <div className="band-spacer" />

        <div className="row" style={{ gap: 14 }}>
          <span className="row" style={{ gap: 6 }}>
            <span className="label label-faint">UTC</span>
            <span className="mono dim" style={{ fontSize: 11 }}>
              {clock}
            </span>
          </span>
          <StatusChip
            tone={gatewayReachable === false ? "warn" : gatewayReachable ? "ok" : "idle"}
            title={
              gatewayReachable === null
                ? "Gateway reachability not yet checked."
                : gatewayReachable
                  ? "Gateway responded to the last health check."
                  : "The gateway did not respond to the last health check."
            }
          >
            {gatewayReachable === false ? "Gateway down" : "Gateway"}
          </StatusChip>
          <StatusChip tone={STATE_TONE[state]}>{state}</StatusChip>
        </div>
      </div>

      {/* Row 1 — mission breadcrumb + environment */}
      <div className="band" style={{ height: 30 }}>
        <div className="row" style={{ gap: 18 }}>
          <TelemetryPair label="Mission" value={missionId} />
          <TelemetryPair label="Run" value={runId} />
        </div>

        <div className="band-spacer" />

        <div className="row" style={{ gap: 14 }}>
          <TelemetryPair
            label="Env"
            value={source === "fixture" ? "DEMO" : "LIVE"}
            tone={source === "fixture" ? "amb" : undefined}
          />
        </div>
      </div>
    </header>
  );
}

function TelemetryPair({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | null;
  tone?: "amb";
}) {
  return (
    <span className="row" style={{ gap: 6 }}>
      <Label faint>{label}</Label>
      <span className={`mono ${tone ?? "dim"}`} style={{ fontSize: 10 }}>
        {value ?? "—"}
      </span>
    </span>
  );
}
