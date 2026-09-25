"use client";

/**
 * The report (P5-14).
 *
 * This is the artefact that leaves the system, so it is built to a different rule
 * than the console: everything on it must be traceable to something measured, and
 * anything not measured must say so in the report itself rather than being dropped.
 * A reader who was not in the room has only this page.
 *
 * Laid out as an intelligence product — a header block of identifiers, numbered
 * sections, a provenance footer — not as a PDF preview with a toolbar. It prints:
 * the print stylesheet drops the chrome and lets sections break cleanly, because
 * the first thing anyone does with a report like this is print it or PDF it.
 */

import { motion, useReducedMotion } from "framer-motion";

import { confidenceBand, formatPercent, formatUTC } from "../../lib/geo/format";
import {
  Label,
  NotAvailable,
  ProvenanceBadge,
  Readout,
  StatusChip,
} from "../system/primitives";
import type { ConsoleScenario } from "../../lib/model/console";
import type { DataSource } from "../../lib/api/source";

export interface ReportViewProps {
  scenario: ConsoleScenario;
  source: DataSource;
  generatedAt: string;
  onExport?: () => void;
}

export function ReportView({
  scenario,
  source,
  generatedAt,
  onExport,
}: ReportViewProps) {
  const reduce = useReducedMotion();
  const { change, confidence, comparison, arbitration, evidence, monitoring } =
    scenario;

  return (
    <article className="report">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="report-head">
        <div className="row" style={{ gap: 12 }}>
          <Label>SatQuery</Label>
          <Label faint>Geospatial analysis report</Label>
          <div className="band-spacer" />
          <ProvenanceBadge source={source} />
          <button className="btn no-print" onClick={() => window.print()}>
            Print
          </button>
          {onExport ? (
            <button className="btn no-print" onClick={onExport}>
              Export
            </button>
          ) : null}
        </div>

        <h1
          className="heading"
          style={{ fontSize: 22, margin: "14px 0 4px", letterSpacing: "-0.015em" }}
        >
          {change.headline}
        </h1>
        <p className="mono dim" style={{ margin: 0, fontSize: 11 }}>
          {scenario.aoiName}
        </p>

        <div className="report-ids">
          <Readout label="Mission" value={scenario.missionId} />
          <Readout label="Run" value={scenario.runId} />
          <Readout label="Trace" value={scenario.traceId} />
          <Readout label="Generated" value={formatUTC(generatedAt)} />
        </div>
      </header>

      <Section n={1} title="Summary" reduce={reduce}>
        <p className="report-prose">
          Surface water over the {scenario.aoiName} rose from{" "}
          <strong>{formatPercent(change.baselineFraction)}</strong> of the analysed
          area to{" "}
          <strong>
            {formatPercent(change.baselineFraction + change.changeFraction)}
          </strong>
          , an increase of <strong>{change.areaSqKm.toFixed(2)} km²</strong> across{" "}
          {change.polygonCount} distinct polygons. The measurement is made from a
          Sentinel-1 synthetic-aperture radar acquisition, compared against the
          multi-year permanent-water baseline.
        </p>
        <p className="report-prose">
          <strong>
            {formatPercent(1 - change.coverageFraction)} of the area of interest fell
            outside the sensor swath and was not analysed.
          </strong>{" "}
          Every figure in this report describes the{" "}
          {formatPercent(change.coverageFraction)} that was.
        </p>
      </Section>

      <Section n={2} title="Area of interest" reduce={reduce}>
        {/* A label/value pair stretched across 830px is unreadable — the eye loses
            the row. Two columns keep each pair within a scannable span. */}
        <div className="report-grid">
          <Readout label="Name" value={scenario.aoiName} />
          <Readout label="Area" value={`${scenario.aoiAreaSqKm.toFixed(1)} km²`} />
          <Readout label="CRS" value="EPSG:4326" />
          <Readout
            label="Bounds"
            value={comparison.after.bbox.map((v) => v.toFixed(4)).join(", ")}
          />
        </div>
      </Section>

      <Section n={3} title="Observations" reduce={reduce}>
        <div className="report-grid">
          <ObservationBlock
            title="Analysed observation"
            obs={comparison.after}
          />
          <ObservationBlock
            title="Compared against"
            obs={comparison.before}
            fallbackReason={comparison.beforeUnavailableReason}
          />
        </div>
        {comparison.beforeUnavailableReason ? (
          <p className="report-note">
            No pre-event acquisition was available. This is a comparison against a
            baseline, not a bi-temporal change detection, and must not be read as
            one. {comparison.beforeUnavailableReason}
          </p>
        ) : null}
      </Section>

      <Section n={4} title="Change" reduce={reduce}>
        <div className="report-grid">
          <Figure
            label="New water"
            value={`${change.areaSqKm.toFixed(2)} km²`}
            tone="signal"
          />
          <Figure label="Polygons" value={String(change.polygonCount)} />
          <Figure
            label="Baseline"
            value={formatPercent(change.baselineFraction)}
          />
          <Figure
            label="Observed"
            value={formatPercent(change.baselineFraction + change.changeFraction)}
          />
        </div>
        {comparison.after.imageUrl ? (
          <figure className="report-figure">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={scenario.overlays.change?.url ?? comparison.after.imageUrl}
              alt="Sentinel-1 backscatter with newly inundated area tinted."
            />
            <figcaption className="mono faint">
              Sentinel-1 VV backscatter. Tinted area is water present in the
              observation but absent from the permanent-water baseline. Transparent
              regions fall outside the swath.
            </figcaption>
          </figure>
        ) : null}
      </Section>

      <Section n={5} title="Confidence and uncertainty" reduce={reduce}>
        <div className="row" style={{ gap: 14, alignItems: "baseline" }}>
          <span className="counter" style={{ fontSize: 30 }}>
            {formatPercent(confidence.score)}
          </span>
          <Label>{confidenceBand(confidence.score)}</Label>
          <StatusChip tone={confidence.passedGate ? "ok" : "warn"}>
            {confidence.passedGate ? "Above gate" : "Below gate"}
          </StatusChip>
        </div>
        <p className="report-prose" style={{ marginTop: 10 }}>
          The score is not a probability. Calibration was measured and{" "}
          <strong>did not pass</strong>: expected calibration error is 0.058 against
          a 0.05 bar, so this value orders results reliably but should not be read as
          &ldquo;87% likely&rdquo;.
        </p>
        <Label faint>Named uncertainty factors</Label>
        <ol className="report-list">
          {confidence.uncertaintyFactors.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ol>
        <div style={{ maxWidth: 520 }}>
          <Readout label="Action taken" value={confidence.action} />
        </div>
      </Section>

      <Section n={6} title="Sensor arbitration" reduce={reduce}>
        <table className="report-table">
          <thead>
            <tr>
              <th>Sensor</th>
              <th>Finding</th>
              <th>Confidence</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {arbitration.readings.map((r) => (
              <tr key={r.sensor}>
                <td className="mono">{r.sensor}</td>
                <td>{r.finding}</td>
                <td className="mono">
                  {r.confidence === null ? "—" : r.confidence.toFixed(2)}
                </td>
                <td>
                  {r.sensor === arbitration.primary
                    ? "Primary"
                    : r.sensor === arbitration.secondary
                      ? "Corroborating"
                      : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {arbitration.rationale ? (
          <p className="report-prose">{arbitration.rationale}</p>
        ) : (
          <NotAvailable reason="The agent did not return a rationale." />
        )}
      </Section>

      <Section n={7} title="Evidence chain" reduce={reduce}>
        <table className="report-table">
          <tbody>
            {evidence.map((node, i) => (
              <tr key={node.id}>
                <td className="mono faint" style={{ width: 28 }}>
                  {String(i + 1).padStart(2, "0")}
                </td>
                <td style={{ width: 150 }}>
                  <Label>{node.label}</Label>
                </td>
                <td>
                  {node.value ?? (
                    <span className="readout-value-na">
                      NOT AVAILABLE — {node.reason ?? "not supplied"}
                    </span>
                  )}
                  {node.provenance ? (
                    <div className="mono faint" style={{ fontSize: 9.5, marginTop: 2 }}>
                      {node.provenance}
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section n={8} title="Monitoring" reduce={reduce}>
        <div className="report-grid">
          <Readout label="Status" value={monitoring.active ? "ACTIVE" : "OFF"} />
          <Readout
            label="Interval"
            value={monitoring.intervalHours ? `${monitoring.intervalHours} h` : null}
          />
          <Readout
            label="Next observation"
            value={formatUTC(monitoring.nextObservation)}
          />
        </div>
      </Section>

      {/* ── Provenance footer ──────────────────────────────────────────── */}
      <footer className="report-foot">
        <Label faint>Provenance</Label>
        <div className="report-grid" style={{ marginTop: 6 }}>
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
          <Readout label="Dataset" value={comparison.after.dataset} />
          <Readout label="Baseline" value={comparison.before?.dataset ?? null} />
        </div>
        <p className="mono faint" style={{ fontSize: 9.5, marginTop: 10, lineHeight: 1.6 }}>
          Model performance, measured on regions held out of training entirely
          (India and Somalia): pooled IoU 0.435 against a classical Otsu log-ratio
          baseline at 0.204. Accuracy is not reported for this task — water is
          roughly 11% of pixels, so a model predicting no water anywhere scores 89%.
          {source === "fixture"
            ? " This report was generated from a deterministic demo fixture and is not a live analysis."
            : ""}
        </p>
      </footer>
    </article>
  );
}

function Section({
  n,
  title,
  children,
  reduce,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
  reduce: boolean | null;
}) {
  return (
    <motion.section
      className="report-section"
      initial={reduce ? false : { opacity: 0, y: 4 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: reduce ? 0 : 0.25 }}
    >
      <div className="row" style={{ gap: 10, marginBottom: 8 }}>
        <span className="mono faint" style={{ fontSize: 10 }}>
          {String(n).padStart(2, "0")}
        </span>
        <Label as="h2">{title}</Label>
      </div>
      {children}
    </motion.section>
  );
}

function Figure({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "signal";
}) {
  return (
    <div style={{ borderLeft: "1px solid var(--hairline)", paddingLeft: 10 }}>
      <Label faint>{label}</Label>
      <div
        className="counter"
        style={{ fontSize: 19, marginTop: 2, color: tone === "signal" ? "var(--signal)" : undefined }}
      >
        {value}
      </div>
    </div>
  );
}

function ObservationBlock({
  title,
  obs,
  fallbackReason,
}: {
  title: string;
  obs: import("../../lib/model/console").Observation | null;
  fallbackReason?: string;
}) {
  return (
    <div>
      <Label>{title}</Label>
      {!obs ? (
        <div style={{ marginTop: 4 }}>
          <NotAvailable reason={fallbackReason} />
        </div>
      ) : (
        <div style={{ marginTop: 4 }}>
          <Readout label="Sensor" value={obs.sensor} />
          <Readout
            label="Acquired"
            value={obs.acquired ? formatUTC(obs.acquired) : null}
            reason={obs.acquiredUnavailableReason}
          />
          <Readout label="Dataset" value={obs.dataset} />
          <Readout label="GSD" value={obs.resolutionM ? `${obs.resolutionM} m` : null} />
        </div>
      )}
    </div>
  );
}
