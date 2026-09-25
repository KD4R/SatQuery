"use client";

/**
 * The report route (P5-14).
 *
 * Owns the generate/ready lifecycle and then hands off to ReportView. The report
 * only renders once a job has actually produced one — there is no "preview" of an
 * ungenerated report, because a page that looks like a finished report before the
 * analysis has run is the most dangerous kind of fake progress on this product.
 */

import { useState } from "react";

import { ASSAM_SCENARIO, FIXTURE_EPOCH } from "../../lib/fixtures";
import { demoModeEnabled } from "../../lib/api/source";
import { EmptyState } from "../system/ErrorBoundary";
import { Label } from "../system/primitives";
import { ReportGenerator, type ReportPhase } from "./ReportGenerator";
import { ReportView } from "./ReportView";
import { RouteChrome } from "../shell/RouteChrome";

export function ReportScreen({ missionId }: { missionId: string }) {
  const demo = demoModeEnabled();
  const [phase, setPhase] = useState<ReportPhase>("idle");

  const known = demo && missionId === ASSAM_SCENARIO.missionId;

  return (
    <RouteChrome title="Report">
      {phase === "ready" && known ? (
        <ReportView
          scenario={ASSAM_SCENARIO}
          source="fixture"
          generatedAt={FIXTURE_EPOCH}
        />
      ) : (
        <div style={{ maxWidth: 560, margin: "0 auto", padding: "48px 20px" }}>
          <Label faint>Mission</Label>
          <p className="mono" style={{ margin: "4px 0 20px", fontSize: 12 }}>
            {missionId}
          </p>

          {!known && demo ? (
            <EmptyState
              title="No report for this mission"
              hint="Only the demo mission has a fixture report"
            />
          ) : (
            <>
              <p
                style={{
                  fontSize: 12.5,
                  lineHeight: 1.6,
                  color: "var(--ink-dim)",
                  margin: "0 0 16px",
                }}
              >
                Report generation is asynchronous. Submitting returns a job; the
                report renders when that job completes.
              </p>
              <ReportGenerator
                demo={demo}
                phase={phase}
                setPhase={setPhase}
                onReady={() => undefined}
              />
            </>
          )}
        </div>
      )}
    </RouteChrome>
  );
}
