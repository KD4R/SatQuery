"use client";

/**
 * The right rail (P5-08 … P5-13).
 *
 * One scrolling column of sections rather than tabs, because the operator's
 * question is usually "why should I believe this", and an answer split across four
 * tabs is an answer nobody reads. Order is deliberate: what changed, how sure we
 * are, why it was flagged, what the sensors said, what happened before.
 *
 * Confidence is never rendered as a bare percentage. The PRD is explicit that
 * uncertainty must be explained, so the score always appears with its band, its
 * coverage, and the named factors holding it down.
 */

import dynamic from "next/dynamic";
import { motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";

import {
  confidenceBand,
  formatPercent,
  formatUTC,
} from "../../lib/geo/format";
import { buildEvidenceGraph } from "../../lib/evidence/graph";
import { buildImpactModel } from "../../lib/impact/model";
import {
  Label,
  NotAvailable,
  Panel,
  PanelSection,
  ProvenanceBadge,
  Readout,
  StatusChip,
} from "../system/primitives";
import { BeforeAfterViewer } from "../observe/BeforeAfterViewer";
import { InfrastructureImpact } from "../impact/InfrastructureImpact";
import type { ConsoleScenario } from "../../lib/model/console";
import type { DataSource } from "../../lib/api/source";

/**
 * React Flow is ~100 kB of canvas code. Like MapWorkspace, it is loaded on demand
 * and only when the operator opens the drawer, so the console's first-load budget
 * is untouched (P5-16). ssr:false because it measures the DOM.
 */
const EvidenceGraphDrawer = dynamic(
  () => import("./EvidenceGraphDrawer").then((m) => m.EvidenceGraphDrawer),
  {
    ssr: false,
    loading: () => (
      <div className="egraph-loading">
        <span className="label label-faint">Loading evidence graph…</span>
      </div>
    ),
  },
);

export function IntelligencePanel({
  scenario,
  source,
  sourceAt,
  revealed,
}: {
  scenario: ConsoleScenario | null;
  source: DataSource;
  sourceAt?: string;
  /** False until the run completes, so nothing is shown before it is known. */
  revealed: boolean;
}) {
  const reduce = useReducedMotion();
  const [graphOpen, setGraphOpen] = useState(false);

  // Escape closes the drawer. Owned here so the trigger keeps focus semantics in
  // one place rather than reaching into the lazily loaded canvas.
  useEffect(() => {
    if (!graphOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setGraphOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [graphOpen]);

  const openGraph = useCallback(() => setGraphOpen(true), []);
  const closeGraph = useCallback(() => setGraphOpen(false), []);

  if (!scenario || !revealed) {
    return (
      <Panel title="Intelligence">
        <div style={{ padding: 24, textAlign: "center" }}>
          <p className="label label-faint" style={{ lineHeight: 1.8 }}>
            No analysis yet
            <br />
            Run a mission to populate this panel
          </p>
        </div>
      </Panel>
    );
  }

  const { change, confidence, arbitration, evidence, comparison, monitoring } =
    scenario;
  const band = confidenceBand(confidence.score);
  const impactModel = buildImpactModel(scenario);

  return (
    <Panel
      title="Intelligence"
      actions={<ProvenanceBadge source={source} at={sourceAt} />}
    >
      <motion.div
        initial={reduce ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: reduce ? 0 : 0.18 }}
      >
        {/* ── Observation comparison ─────────────────────────────────────── */}
        <BeforeAfterViewer
          pair={comparison}
          beforeLabel="Permanent baseline"
          afterLabel="Observed"
        />

        {/* ── Change ─────────────────────────────────────────────────────── */}
        <PanelSection title="Change">
          <p style={{ margin: "0 0 8px", fontSize: 12.5, lineHeight: 1.5 }}>
            {change.headline}
          </p>
          <Readout label="New water" value={`${change.areaSqKm.toFixed(2)} km²`} tone="signal" />
          <Readout label="Polygons" value={String(change.polygonCount)} />
          <Readout
            label="Baseline → observed"
            value={`${formatPercent(change.baselineFraction)} → ${formatPercent(
              change.baselineFraction + change.changeFraction,
            )}`}
          />
          <Readout
            label="Coverage"
            value={formatPercent(change.coverageFraction)}
            tone={change.coverageFraction < 0.6 ? "amber" : undefined}
          />
          {change.coverageFraction < 0.6 ? (
            <p className="mono amb" style={{ fontSize: 10, margin: "6px 0 0", lineHeight: 1.45 }}>
              ▲ {formatPercent(1 - change.coverageFraction)} of the AOI was outside the
              swath and was not analysed. Figures describe the analysed part only.
            </p>
          ) : null}
        </PanelSection>

        {/* ── Infrastructure impact (PRD §2D) ────────────────────────────── */}
        <InfrastructureImpact model={impactModel} />

        {/* ── Confidence (P5-11) ─────────────────────────────────────────── */}
        <PanelSection
          title="Confidence"
          actions={
            <StatusChip tone={confidence.passedGate ? "ok" : "warn"}>
              {confidence.passedGate ? "Above gate" : "Below gate"}
            </StatusChip>
          }
        >
          <div className="row" style={{ alignItems: "baseline", gap: 10, marginBottom: 8 }}>
            <span className="counter" style={{ fontSize: 28, lineHeight: 1 }}>
              {formatPercent(confidence.score)}
            </span>
            <span
              className="label"
              style={{
                color:
                  band === "HIGH"
                    ? "var(--verified)"
                    : band === "MODERATE"
                      ? "var(--amber)"
                      : "var(--signal)",
              }}
            >
              {band}
            </span>
          </div>

          <Readout
            label="Uncertain area"
            value={
              confidence.uncertainFraction === null
                ? null
                : formatPercent(confidence.uncertainFraction)
            }
            reason="The model did not report a per-pixel uncertainty mask."
          />
          <Readout label="Action" value={confidence.action} />

          <div style={{ marginTop: 8 }}>
            <Label faint>Why it is not higher</Label>
            {confidence.uncertaintyFactors.length === 0 ? (
              <NotAvailable reason="No uncertainty factors were reported." />
            ) : (
              <ul style={{ margin: "4px 0 0", padding: 0, listStyle: "none" }}>
                {confidence.uncertaintyFactors.map((f) => (
                  <li
                    key={f}
                    className="mono"
                    style={{
                      fontSize: 10,
                      lineHeight: 1.5,
                      color: "var(--ink-dim)",
                      paddingLeft: 12,
                      position: "relative",
                      marginBottom: 3,
                    }}
                  >
                    <span style={{ position: "absolute", left: 0, color: "var(--amber)" }}>
                      ▲
                    </span>
                    {f}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </PanelSection>

        {/* ── WHY (P5-09, PRD §2B) ────────────────────────────────────────── */}
        <PanelSection
          title="Why this was flagged"
          actions={
            <button
              type="button"
              className="egraph-trigger"
              onClick={openGraph}
              aria-haspopup="dialog"
              aria-expanded={graphOpen}
            >
              ▣ WHY GRAPH
            </button>
          }
        >
          {evidence.map((node, i) => (
            <div
              key={node.id}
              style={{
                paddingBottom: 7,
                marginBottom: 7,
                borderBottom:
                  i === evidence.length - 1 ? "none" : "1px solid var(--hairline)",
              }}
            >
              <div className="row" style={{ gap: 7, alignItems: "baseline" }}>
                <span className="mono faint" style={{ fontSize: 9, width: 14 }}>
                  {String(i + 1).padStart(2, "0")}
                </span>
                <Label>{node.label}</Label>
              </div>
              <div style={{ paddingLeft: 21, marginTop: 2 }}>
                {node.value ? (
                  <p style={{ margin: 0, fontSize: 11.5, lineHeight: 1.5 }}>
                    {node.value}
                  </p>
                ) : (
                  <NotAvailable reason={node.reason} />
                )}
                {node.provenance ? (
                  <p
                    className="mono faint"
                    style={{ margin: "2px 0 0", fontSize: 9.5, lineHeight: 1.45 }}
                  >
                    {node.provenance}
                  </p>
                ) : null}
              </div>
            </div>
          ))}
        </PanelSection>

        {/* The drawer lives after the sections so its fixed overlay mounts above
            the panel content; the graph is derived from the same scenario. */}
        {graphOpen && scenario ? (
          <EvidenceGraphDrawer
            graph={buildEvidenceGraph(scenario)}
            open={graphOpen}
            onClose={closeGraph}
          />
        ) : null}

        {/* ── Sensor arbitration (P5-10) ─────────────────────────────────── */}
        <PanelSection
          title="Sensor arbitration"
          actions={
            arbitration.disagreement ? (
              <StatusChip tone="warn">Disagreement</StatusChip>
            ) : (
              <StatusChip tone="ok">Agreement</StatusChip>
            )
          }
        >
          {arbitration.readings.map((r) => {
            const isPrimary = r.sensor === arbitration.primary;
            return (
              <div
                key={r.sensor}
                style={{
                  border: "1px solid var(--hairline)",
                  borderLeft: `2px solid ${isPrimary ? "var(--signal)" : "var(--hairline-bright)"}`,
                  padding: 7,
                  marginBottom: 6,
                }}
              >
                <div className="row" style={{ gap: 7 }}>
                  <span className="label" style={{ color: "var(--ink)" }}>
                    {r.sensor}
                  </span>
                  <div className="band-spacer" />
                  {isPrimary ? <StatusChip tone="active">Primary</StatusChip> : null}
                </div>
                <div className="readout">
                  <Label faint>Finding</Label>
                  <span className="readout-value">{r.finding}</span>
                </div>
                <Readout
                  label="Confidence"
                  value={r.confidence === null ? null : r.confidence.toFixed(2)}
                  reason="This sensor did not return a score."
                />
                <p
                  className="mono faint"
                  style={{ margin: "4px 0 0", fontSize: 10, lineHeight: 1.45 }}
                >
                  {r.note}
                </p>
              </div>
            );
          })}

          <div style={{ marginTop: 6 }}>
            <Label faint>Verdict</Label>
            {arbitration.rationale ? (
              <p style={{ margin: "3px 0 0", fontSize: 11.5, lineHeight: 1.5 }}>
                {arbitration.rationale}
              </p>
            ) : (
              <NotAvailable reason="The agent did not return a rationale." />
            )}
            <Readout
              label="Arbitration score"
              value={
                arbitration.arbitrationScore === null
                  ? null
                  : arbitration.arbitrationScore.toFixed(2)
              }
            />
          </div>
        </PanelSection>

        {/* ── Monitoring (P5-13) ─────────────────────────────────────────── */}
        <PanelSection
          title="Monitoring"
          actions={
            <StatusChip tone={monitoring.active ? "active" : "idle"}>
              {monitoring.active ? "Active" : "Off"}
            </StatusChip>
          }
        >
          <Readout label="AOI" value={monitoring.aoiName} />
          <Readout
            label="Interval"
            value={monitoring.intervalHours ? `${monitoring.intervalHours} h` : null}
          />
          <Readout label="Last observation" value={formatUTC(monitoring.lastObservation)} />
          <Readout label="Next observation" value={formatUTC(monitoring.nextObservation)} />
          <Readout
            label="Change status"
            value={monitoring.changeStatus}
            tone={monitoring.changeStatus === "INCREASING" ? "signal" : undefined}
          />
        </PanelSection>

        {/* ── Provenance (P5-14 inputs) ──────────────────────────────────── */}
        <PanelSection title="Provenance">
          <Readout label="Mission" value={scenario.missionId} />
          <Readout label="Run" value={scenario.runId} />
          <Readout label="Trace" value={scenario.traceId} />
          <Readout
            label="Model"
            value={scenario.modelVersion}
            reason="The inference service did not report a model version."
          />
          <Readout
            label="Processing"
            value={scenario.processingVersion}
            reason="The preprocessing service did not report a version."
          />
        </PanelSection>
      </motion.div>
    </Panel>
  );
}
