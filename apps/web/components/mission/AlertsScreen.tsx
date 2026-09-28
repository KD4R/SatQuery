"use client";

/**
 * Alerts and events (P5-13 adjacent).
 *
 * No alert feed is contracted at the gateway: the only live event stream is the
 * per-mission agent WebSocket, which the console renders as toasts while a run is
 * going. So in live mode this screen says that. In demo it lists the pinned agent
 * narratives the demo run emits, with the fixture badge and their offset into the
 * run — never a wall-clock time, because none exists.
 *
 * Replaces a page of invented alerts ("Cloud fraction reached 67%", "31 min ago").
 */

import Link from "next/link";

import { DEMO_AGENT_EVENTS, FIXTURE_EPOCH } from "../../lib/fixtures";
import { demoModeEnabled } from "../../lib/api/source";
import { ROUTES } from "../../lib/nav";
import PageShell from "../PageShell";
import SectionHeader from "../SectionHeader";
import { ProvenanceBadge } from "../system/primitives";
import { EmptyState } from "../system/ErrorBoundary";

const KIND: Record<string, string> = {
  SENSOR_DISAGREEMENT: "Sensor disagreement",
  SENSOR_AGREEMENT: "Sensors agree",
  ACQUIRING_EVIDENCE: "Acquiring evidence",
  AGENT_THOUGHT: "Agent",
};

export function AlertsScreen() {
  const demo = demoModeEnabled();

  return (
    <PageShell>
      <SectionHeader
        eyebrow="07 / EVENTS"
        title="Alerts & events"
        description="What the agent said while a mission ran. Live events arrive over the mission socket and are shown as toasts on the console."
        action={{ label: "Open mission console", href: ROUTES.console }}
      />

      {demo ? (
        <div className="surface">
          <div className="surface-title">
            <h2>Demo run events</h2>
            <ProvenanceBadge source="fixture" at={FIXTURE_EPOCH} />
          </div>
          {DEMO_AGENT_EVENTS.map((e) => (
            <div
              className={`alert-item${e.type === "SENSOR_DISAGREEMENT" ? " warning" : ""}`}
              key={e.atMs}
            >
              <b>{KIND[e.type] ?? e.type}</b>
              <small>
                {e.message} · T+{(e.atMs / 1000).toFixed(1)} s into the run
              </small>
            </div>
          ))}
        </div>
      ) : (
        <div className="surface">
          <EmptyState
            title="No alert feed is contracted"
            hint="The gateway publishes no alerts route. Agent events for a running mission appear as toasts on the console."
          />
          <p style={{ textAlign: "center" }}>
            <Link className="ghost-btn" href={ROUTES.console}>
              Go to the mission console
            </Link>
          </p>
        </div>
      )}
    </PageShell>
  );
}
