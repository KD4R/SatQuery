"use client";

/**
 * Mission memory (P5-12).
 *
 * A satellite intelligence timeline, not an activity feed. The difference is the
 * axis: events are laid against elapsed time with the gaps visible, so a run
 * followed by silence for a day reads as silence for a day rather than as two
 * adjacent rows. That is what lets an operator see cadence.
 *
 * Live missions come from GET /api/v1/missions, which the gateway does expose. The
 * per-mission event detail does not exist as a route yet, so in live mode each
 * mission lists what the gateway actually returns and says the rest is unavailable
 * rather than inventing a history.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { ASSAM_SCENARIO } from "../../lib/fixtures";
import { GatewayError } from "../../lib/api/gateway";
import { demoModeEnabled } from "../../lib/api/source";
import { formatUTC } from "../../lib/geo/format";
import { listMissions } from "../../lib/api/client";
import type { ErrorResponse, MissionResponse } from "../../lib/api/types";
import type { MissionEvent } from "../../lib/model/console";
import { EmptyState, ErrorState, LoadingState } from "../system/ErrorBoundary";
import { Label, Readout, StatusChip } from "../system/primitives";
import { RouteChrome } from "../shell/RouteChrome";

const KIND_TONE = {
  run: "active",
  observation: "idle",
  detection: "warn",
  monitoring: "ok",
  report: "idle",
} as const;

export function MissionMemory() {
  const demo = demoModeEnabled();
  const [missions, setMissions] = useState<MissionResponse[] | null>(null);
  const [error, setError] = useState<ErrorResponse | null>(null);

  useEffect(() => {
    if (demo) return;
    const controller = new AbortController();
    listMissions(controller.signal)
      .then((r) => setMissions(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(
          e instanceof GatewayError
            ? e.body
            : { code: "unknown", message: "Missions could not be loaded.", trace_id: null },
        );
      });
    return () => controller.abort();
  }, [demo]);

  return (
    <RouteChrome title="Mission memory">
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "20px 20px 60px" }}>
        {demo ? (
          <DemoMemory />
        ) : error ? (
          <ErrorState title="Missions unavailable" error={error} />
        ) : missions === null ? (
          <LoadingState label="Loading missions" />
        ) : missions.length === 0 ? (
          <EmptyState title="No missions yet" hint="Run one from the console" />
        ) : (
          <LiveMissions missions={missions} />
        )}
      </div>
    </RouteChrome>
  );
}

function LiveMissions({ missions }: { missions: MissionResponse[] }) {
  return (
    <div>
      <Label>Missions</Label>
      <div style={{ marginTop: 10 }}>
        {missions.map((m) => (
          <div
            key={m.id}
            style={{
              padding: "10px 0",
              borderBottom: "1px solid var(--hairline)",
            }}
          >
            <div className="row" style={{ gap: 10 }}>
              <span style={{ fontSize: 13 }}>{m.name}</span>
              <div className="band-spacer" />
              <StatusChip
                tone={
                  m.status === "running"
                    ? "active"
                    : m.status === "failed"
                      ? "warn"
                      : m.status === "completed"
                        ? "ok"
                        : "idle"
                }
              >
                {m.status}
              </StatusChip>
            </div>
            <Readout label="Mission" value={m.id} />
            <Readout label="Updated" value={formatUTC(m.updated_at)} />
            <Readout
              label="Run history"
              value={null}
              reason="The gateway exposes no per-mission run history route yet (P5-12 depends on it)."
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function DemoMemory() {
  const reduce = useReducedMotion();
  const s = ASSAM_SCENARIO;
  const events: MissionEvent[] = [...s.history, ...s.monitoring.recentEvents].sort(
    (a, b) => (a.at < b.at ? 1 : -1),
  );

  // Gaps between events, as a fraction of the longest gap. Drawing the gap is what
  // makes this a timeline rather than a list.
  const times = events.map((e) => new Date(e.at).getTime());
  const gaps = times.slice(0, -1).map((t, i) => t - (times[i + 1] as number));
  const maxGap = Math.max(1, ...gaps);

  return (
    <div>
      <div className="row" style={{ marginBottom: 14 }}>
        <div>
          <h1 className="heading" style={{ fontSize: 17, margin: 0 }}>
            {s.aoiName}
          </h1>
          <p className="mono faint" style={{ margin: "2px 0 0", fontSize: 10 }}>
            {s.missionId}
          </p>
        </div>
        <div className="band-spacer" />
        <Link
          href={`/missions/${s.missionId}/report`}
          className="btn btn-primary"
        >
          View report
        </Link>
      </div>

      <Label faint>Temporal history</Label>

      <div style={{ marginTop: 10 }}>
        {events.map((e, i) => {
          const gap = i < gaps.length ? (gaps[i] as number) : 0;
          // 14px minimum so adjacent events stay legible; 88px ceiling so a long
          // quiet period does not push everything off the screen.
          const gapPx = Math.round(14 + (gap / maxGap) * 74);
          return (
            <motion.div
              key={e.id}
              initial={reduce ? false : { opacity: 0, x: -4 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: reduce ? 0 : i * 0.05, duration: 0.25 }}
            >
              <div style={{ display: "grid", gridTemplateColumns: "128px 20px 1fr" }}>
                <div className="mono faint" style={{ fontSize: 10, paddingTop: 1 }}>
                  {formatUTC(e.at)}
                </div>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      marginTop: 5,
                      borderRadius: "50%",
                      background:
                        e.kind === "detection" ? "var(--signal)" : "var(--ink-faint)",
                    }}
                  />
                </div>
                <div>
                  <div className="row" style={{ gap: 8 }}>
                    <span style={{ fontSize: 12.5 }}>{e.summary}</span>
                    <StatusChip tone={KIND_TONE[e.kind]}>{e.kind}</StatusChip>
                  </div>
                  {e.detail ? (
                    <p
                      className="mono faint"
                      style={{ margin: "1px 0 0", fontSize: 10, lineHeight: 1.45 }}
                    >
                      {e.detail}
                    </p>
                  ) : null}
                </div>
              </div>

              {i < events.length - 1 ? (
                <div style={{ display: "grid", gridTemplateColumns: "128px 20px 1fr" }}>
                  <div />
                  <div style={{ display: "flex", justifyContent: "center" }}>
                    <span
                      style={{
                        width: 1,
                        height: gapPx,
                        background: "var(--hairline)",
                      }}
                    />
                  </div>
                  <div
                    className="mono"
                    style={{
                      fontSize: 9,
                      color: "var(--ink-ghost)",
                      alignSelf: "center",
                    }}
                  >
                    {gap > 0 ? `+${Math.round(gap / 3_600_000)} h` : ""}
                  </div>
                </div>
              ) : null}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
