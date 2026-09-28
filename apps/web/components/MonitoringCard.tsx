"use client";

import Link from "next/link";
import { BellRing, CalendarClock, RadioTower } from "lucide-react";

import { demoModeEnabled } from "../lib/api/source";
import { ROUTES } from "../lib/nav";

/**
 * Entry point to persistent monitoring (P5-13).
 *
 * This card used to flip a local "Active / Paused" switch that started nothing,
 * over a hard-coded "Flood watch · Guntur, next window 24 Sep". A control that
 * changes its own label but no backend state is fake progress, so it is gone: the
 * card now says what monitoring is available here and links to the screen that
 * owns it.
 */
export default function MonitoringCard() {
  const demo = demoModeEnabled();
  return (
    <section className="card monitoring-card">
      <div className="card-head">
        <div>
          <div className="title-row">
            <RadioTower size={14} />
            <div className="card-title">PERSISTENT MONITORING</div>
          </div>
          <div className="card-sub">Turn one mission into a watch</div>
        </div>
        <span className="status-dot-label">
          <i />
          {demo ? "Fixture watch" : "Not contracted"}
        </span>
      </div>
      <div className="monitor-row">
        <div>
          <b>{demo ? "Flood watch over the demo AOI" : "No monitoring route yet"}</b>
          <span>
            {demo
              ? "Cadence, countdown and change status come from the pinned scenario."
              : "The gateway exposes no monitoring route, so no watch can be created or listed."}
          </span>
        </div>
        <Link className="primary-small" href={ROUTES.monitoring}>
          Open monitoring
        </Link>
      </div>
      <div className="monitor-meta">
        <span>
          <CalendarClock size={12} /> Cadence shown on the monitoring screen
        </span>
        <span>
          <BellRing size={12} /> Alerts are gated on material change
        </span>
      </div>
    </section>
  );
}
