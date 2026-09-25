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
      {/* Row 1 — identity, centred wordmark, system state */}
      <div className="band">
        <div className="row" style={{ gap: 14 }}>
          <Label>SatQuery</Label>
          <Label faint>Mission Console</Label>
        </div>

        <div className="band-spacer" />

        <span
          className="heading"
          style={{ fontSize: 13, letterSpacing: "0.22em", fontWeight: 700 }}
        >
          SATQUERY
        </span>

        <div className="band-spacer" />

        <div className="row" style={{ gap: 8 }}>
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
            Gateway
          </StatusChip>
          <StatusChip tone={STATE_TONE[state]}>{state}</StatusChip>
        </div>
      </div>

      {/* Row 2 — mission telemetry */}
      <div className="band" style={{ height: 26 }}>
        <div className="row" style={{ gap: 18 }}>
          <TelemetryPair label="Mission" value={missionId} />
          <TelemetryPair label="Run" value={runId} />
        </div>

        <div className="band-spacer" />

        <div className="row" style={{ gap: 18 }}>
          <TelemetryPair
            label="Env"
            value={source === "fixture" ? "DEMO" : "LIVE"}
            tone={source === "fixture" ? "amb" : undefined}
          />
          <TelemetryPair label="UTC" value={clock} />
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
