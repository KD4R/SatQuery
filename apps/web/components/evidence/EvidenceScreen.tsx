"use client";

/**
 * The evidence section (P5-09).
 *
 * Evidence belongs to a run, and the gateway exposes no evidence route of its own:
 * the live agent state carries the graph, which the Mission page renders after a
 * run completes. So this screen has one job per mode:
 *
 *   DEMO  list the pinned scenario's evidence chain, unknowns included, with the
 *         fixture badge — the same rows the WHY graph is built from.
 *   LIVE  say plainly that evidence is per-run and point at where it appears,
 *         instead of listing a plausible-looking chain nobody produced.
 *
 * It replaces a page of hard-coded rows (run "SAT-2409", dataset "S1-Guntur…")
 * that had no source and no badge.
 */

import Link from "next/link";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../../lib/fixtures";
import { demoModeEnabled } from "../../lib/api/source";
import { ROUTES } from "../../lib/nav";
import PageShell from "../PageShell";
import SectionHeader from "../SectionHeader";
import { NotAvailable, ProvenanceBadge } from "../system/primitives";
import { EmptyState } from "../system/ErrorBoundary";

export function EvidenceScreen() {
  const demo = demoModeEnabled();

  return (
    <PageShell>
      <SectionHeader
        eyebrow="04 / PROVENANCE"
        title="Evidence chain"
        description="The source, decision and measurement behind a mission conclusion. Every row states where it came from, or says it is not available."
        action={{ label: "Open mission console", href: ROUTES.console }}
      />

      {demo ? (
        <div className="surface">
          <div className="surface-title">
            <h2>Correlated evidence</h2>
            <ProvenanceBadge source="fixture" at={FIXTURE_EPOCH} />
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Evidence</th>
                <th scope="col">Kind</th>
                <th scope="col">Value</th>
                <th scope="col">Provenance</th>
              </tr>
            </thead>
            <tbody>
              {ASSAM_SCENARIO.evidence.map((e) => (
                <tr key={e.id}>
                  <td>
                    <b>{e.label}</b>
                  </td>
                  <td>{e.kind}</td>
                  <td>
                    {e.value === null ? <NotAvailable reason={e.reason} /> : e.value}
                  </td>
                  <td>{e.provenance ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="card-sub" style={{ marginTop: 10 }}>
            Mission {ASSAM_SCENARIO.missionId} · trace {ASSAM_SCENARIO.traceId}. The
            WHY graph for this chain opens from the mission console after a run.
          </p>
        </div>
      ) : (
        <div className="surface">
          <EmptyState
            title="Evidence is attached to a run"
            hint="Run a mission on the console; its evidence chain appears there when the agent completes. The gateway has no standalone evidence route."
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
