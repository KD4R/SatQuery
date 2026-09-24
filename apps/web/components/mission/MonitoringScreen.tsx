"use client";

/**
 * Persistent monitoring (P5-13).
 *
 * A monitoring screen's job is to answer "is it still watching, and when will it
 * next look" without the operator having to compute anything. So the two headline
 * figures are the countdown to the next pass and the time since the last one, and
 * both are derived from timestamps rather than stored as "3 hours ago" — a string
 * like that is wrong the moment it is written.
 *
 * The countdown is the one live clock on the screen, and it is frozen in demo mode
 * so the page is byte-identical on every run.
 */

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../../lib/fixtures";
import { demoModeEnabled } from "../../lib/api/source";
import { formatUTC } from "../../lib/geo/format";
import { EmptyState } from "../system/ErrorBoundary";
import { Label, Panel, Readout, StatusChip } from "../system/primitives";
import { RouteChrome } from "../shell/RouteChrome";

/** "4h 12m", or null when the instant has passed or is unknown. */
function countdown(toIso: string | null, fromMs: number): string | null {
  if (!toIso) return null;
  const delta = new Date(toIso).getTime() - fromMs;
  if (!Number.isFinite(delta) || delta <= 0) return null;
  const h = Math.floor(delta / 3_600_000);
  const m = Math.floor((delta % 3_600_000) / 60_000);
  return `${h}h ${m.toString().padStart(2, "0")}m`;
}

function elapsed(fromIso: string | null, nowMs: number): string | null {
  if (!fromIso) return null;
  const delta = nowMs - new Date(fromIso).getTime();
  if (!Number.isFinite(delta) || delta < 0) return null;
  const h = Math.floor(delta / 3_600_000);
  const m = Math.floor((delta % 3_600_000) / 60_000);
  return `${h}h ${m.toString().padStart(2, "0")}m`;
}

export function MonitoringScreen() {
  const demo = demoModeEnabled();
  const reduce = useReducedMotion();

  // In demo, "now" is pinned 3h20m after the last observation so the countdown and
  // the elapsed figure are both non-trivial and both identical on every load.
  const pinnedNow = new Date(FIXTURE_EPOCH).getTime() + 3 * 3_600_000 + 20 * 60_000;
  const [nowMs, setNowMs] = useState(pinnedNow);

  useEffect(() => {
    if (demo) return;
    const tick = () => setNowMs(Date.now());
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, [demo]);

  if (!demo) {
    // Honest: the gateway publishes no monitoring route. Saying so, and naming the
    // route that is missing, is more useful than an empty dashboard.
    return (
      <RouteChrome title="Monitoring">
        <div style={{ maxWidth: 620, margin: "0 auto", padding: 40 }}>
          <EmptyState
            title="Monitoring is not contracted yet"
            hint="The gateway exposes no monitoring route; P5-13 depends on one from P2"
          />
          <p
            className="mono faint"
            style={{ fontSize: 10, textAlign: "center", lineHeight: 1.6 }}
          >
            Expected: GET /api/v1/missions/{"{mission_id}"}/monitoring
            <br />
            Run with NEXT_PUBLIC_DEMO_MODE=1 to see the screen against fixtures.
          </p>
        </div>
      </RouteChrome>
    );
  }

  const m = ASSAM_SCENARIO.monitoring;
  const next = countdown(m.nextObservation, nowMs);
  const since = elapsed(m.lastObservation, nowMs);

  return (
    <RouteChrome
      title="Persistent monitoring"
      actions={
        <StatusChip tone={m.active ? "active" : "idle"}>
          {m.active ? "Mission active" : "Idle"}
        </StatusChip>
      }
    >
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "20px 20px 60px" }}>
        <h1 className="heading" style={{ fontSize: 17, margin: "0 0 2px" }}>
          {m.aoiName}
        </h1>
        <p className="mono faint" style={{ margin: 0, fontSize: 10 }}>
          {ASSAM_SCENARIO.missionId}
        </p>

        {/* The two figures the screen exists to answer. */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
            gap: 1,
            background: "var(--hairline)",
            border: "1px solid var(--hairline)",
            margin: "18px 0",
          }}
        >
          <Headline label="Next observation" value={next ?? "DUE NOW"} tone={next ? undefined : "signal"} />
          <Headline label="Since last" value={since ?? "—"} />
          <Headline
            label="Change status"
            value={m.changeStatus}
            tone={m.changeStatus === "INCREASING" ? "signal" : undefined}
          />
          <Headline
            label="Interval"
            value={m.intervalHours ? `${m.intervalHours} h` : "—"}
          />
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 16,
          }}
        >
          <Panel title="Schedule">
            <div style={{ padding: 10 }}>
              <Readout label="Last observation" value={formatUTC(m.lastObservation)} />
              <Readout label="Next observation" value={formatUTC(m.nextObservation)} />
              <Readout
                label="Interval"
                value={m.intervalHours ? `${m.intervalHours} hours` : null}
              />
              <Readout
                label="Revisit guarantee"
                value={null}
                reason="Sentinel-1 revisit depends on orbit and latitude; the backend does not publish a guaranteed cadence."
              />
            </div>
          </Panel>

          <Panel title="Recent events">
            <div style={{ padding: 10 }}>
              {m.recentEvents.map((e, i) => (
                <motion.div
                  key={e.id}
                  initial={reduce ? false : { opacity: 0, y: 3 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: reduce ? 0 : i * 0.06, duration: 0.22 }}
                  style={{
                    paddingBottom: 8,
                    marginBottom: 8,
                    borderBottom:
                      i === m.recentEvents.length - 1
                        ? "none"
                        : "1px solid var(--hairline)",
                  }}
                >
                  <div className="row" style={{ gap: 8 }}>
                    <span style={{ fontSize: 12 }}>{e.summary}</span>
                    <div className="band-spacer" />
                    <span className="mono faint" style={{ fontSize: 9.5 }}>
                      {formatUTC(e.at)}
                    </span>
                  </div>
                  {e.detail ? (
                    <p
                      className="mono faint"
                      style={{ margin: "2px 0 0", fontSize: 10 }}
                    >
                      {e.detail}
                    </p>
                  ) : null}
                </motion.div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </RouteChrome>
  );
}

function Headline({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "signal";
}) {
  return (
    <div style={{ background: "var(--surface-1)", padding: "12px 14px" }}>
      <Label faint>{label}</Label>
      <div
        className="counter"
        style={{
          fontSize: 21,
          marginTop: 4,
          color: tone === "signal" ? "var(--signal)" : "var(--ink)",
        }}
      >
        {value}
      </div>
    </div>
  );
}
