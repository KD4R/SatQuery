"use client";

/**
 * The reports section entry (P5-14): pick a mission, then generate its report.
 *
 * A report is generated from a finished mission, so this screen is a list of
 * missions rather than a set of "Generate" buttons with nothing behind them. Demo
 * offers the one fixture mission; live lists whatever GET /missions returns and
 * says so when that call fails.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { ASSAM_SCENARIO } from "../../lib/fixtures";
import { listMissions } from "../../lib/api/client";
import { GatewayError } from "../../lib/api/gateway";
import { demoModeEnabled } from "../../lib/api/source";
import type { ErrorResponse, MissionResponse } from "../../lib/api/types";
import { ROUTES, reportRoute } from "../../lib/nav";
import PageShell from "../PageShell";
import SectionHeader from "../SectionHeader";
import { EmptyState, ErrorState, LoadingState } from "../system/ErrorBoundary";
import { StatusChip } from "../system/primitives";

export function ReportsIndex() {
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
    <PageShell>
      <SectionHeader
        eyebrow="06 / DECISION BRIEFS"
        title="Reports & decision briefs"
        description="Generate an evidence-backed report from a finished mission. Generation is asynchronous and the report carries its caveats."
        action={{ label: "Open mission console", href: ROUTES.console }}
      />

      <div className="surface">
        <div className="surface-title">
          <h2>Missions</h2>
          {demo ? <StatusChip tone="fixture">Demo fixture</StatusChip> : null}
        </div>

        {demo ? (
          <Link className="list-card" href={reportRoute(ASSAM_SCENARIO.missionId)}>
            <div>
              <b>{ASSAM_SCENARIO.aoiName}</b>
              <small>{ASSAM_SCENARIO.missionId}</small>
            </div>
            <span className="badge success">report</span>
          </Link>
        ) : error ? (
          <ErrorState title="Missions unavailable" error={error} />
        ) : missions === null ? (
          <LoadingState label="Loading missions" />
        ) : missions.length === 0 ? (
          <EmptyState title="No missions yet" hint="Run one from the mission console" />
        ) : (
          missions.map((m) => (
            <Link className="list-card" href={reportRoute(m.id)} key={m.id}>
              <div>
                <b>{m.name}</b>
                <small>
                  {m.id} · {m.status}
                </small>
              </div>
              <span className="badge">report</span>
            </Link>
          ))
        )}
      </div>
    </PageShell>
  );
}
