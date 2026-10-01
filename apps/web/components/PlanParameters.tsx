"use client";

import { ListChecks } from "lucide-react";

import { formatArea } from "../lib/geo/format";
import type { ValidationResult } from "../lib/geo/validate";
import { Label, Readout, StatusChip } from "./system/primitives";

/**
 * The plan the query resolved to (P5-03, P5-06).
 *
 * What the operator typed and what the system understood are both on screen at
 * once — that is the property a chat transcript loses. Every field is a resolved
 * value or NOT AVAILABLE with the reason; a field the planner inferred rather than
 * the operator supplying is marked, so nobody discovers after the fact that the
 * date range was a guess. AOI validation findings that block the run are listed
 * here in words, next to the numbers they concern.
 */

export interface PlanParametersModel {
  aoiName: string | null;
  aoiAreaSqM: number | null;
  dateRange: string | null;
  sensors: string[];
  resolutionM: number | null;
  analysisType: string | null;
  /** Fields the planner inferred rather than the operator supplying them. */
  inferred: ReadonlySet<string>;
}

function Param({
  label,
  value,
  inferred,
  reason,
}: {
  label: string;
  value: string | null;
  inferred: boolean;
  reason: string;
}) {
  return (
    <div className="readout">
      <span className="row" style={{ gap: 6 }}>
        <Label faint>{label}</Label>
        {inferred && value ? (
          <StatusChip tone="idle" title="Inferred by the planner, not supplied by you.">
            inferred
          </StatusChip>
        ) : null}
      </span>
      {value ? (
        <span className="readout-value">{value}</span>
      ) : (
        <span className="readout-value readout-value-na" title={reason}>
          NOT AVAILABLE
        </span>
      )}
    </div>
  );
}

export default function PlanParameters({
  parameters,
  aoiValidation,
}: {
  parameters: PlanParametersModel;
  aoiValidation: ValidationResult;
}) {
  const errors = aoiValidation.findings.filter((f) => f.severity === "error");

  return (
    <section className="sqd-card plan-card" aria-label="Mission plan parameters">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">
          <ListChecks size={13} /> Plan
        </span>
        <span className="sqd-muted-inline">What the system understood</span>
      </header>

      <Param
        label="AOI"
        value={parameters.aoiName}
        inferred={parameters.inferred.has("aoiName")}
        reason="No AOI has been drawn or named."
      />
      <Readout
        label="Area"
        value={parameters.aoiAreaSqM === null ? null : formatArea(parameters.aoiAreaSqM)}
        reason="Draw an AOI to measure it."
      />
      <Param
        label="Date range"
        value={parameters.dateRange}
        inferred={parameters.inferred.has("dateRange")}
        reason="The planner has not resolved a temporal window yet."
      />
      <Param
        label="Sensors"
        value={parameters.sensors.length ? parameters.sensors.join(" · ") : null}
        inferred={parameters.inferred.has("sensors")}
        reason="Sensor arbitration has not run."
      />
      <Readout
        label="Resolution"
        value={parameters.resolutionM === null ? null : `${parameters.resolutionM} m`}
        reason="Depends on the selected observation."
      />
      <Param
        label="Analysis"
        value={parameters.analysisType}
        inferred={parameters.inferred.has("analysisType")}
        reason="The planner has not classified the intent yet."
      />

      {errors.length > 0 ? (
        <div role="alert" style={{ marginTop: 8 }}>
          <Label>AOI blocks this run</Label>
          {errors.map((f) => (
            <p
              key={f.rule}
              className="mono sig"
              style={{ fontSize: 10, margin: "4px 0 0", lineHeight: 1.45 }}
            >
              ✕ {f.message}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  );
}
