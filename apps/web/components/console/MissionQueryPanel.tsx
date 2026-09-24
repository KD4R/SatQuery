"use client";

/**
 * The command interface (P5-03).
 *
 * This is a mission form that happens to take prose, not a chat. There is no
 * message list, no assistant bubble, no avatar and no conversation: the query is a
 * field, the parameters it resolves to are readouts beneath it, and the commit is
 * a single labelled action. What the operator sends and what the system understood
 * are both on screen at once, which is the property a chat transcript loses.
 *
 * Parameters are shown as *resolved* values and marked when they came from the
 * planner rather than from the operator, so nobody discovers after the fact that
 * the date range was inferred.
 */

import { useId, useState } from "react";

import { formatArea } from "../../lib/geo/format";
import { Label, Panel, PanelSection, Readout, StatusChip } from "../system/primitives";
import type { ValidationResult } from "../../lib/geo/validate";

export interface MissionParameters {
  aoiName: string | null;
  aoiAreaSqM: number | null;
  dateRange: string | null;
  sensors: string[];
  resolutionM: number | null;
  analysisType: string | null;
  /** Fields the planner inferred rather than the operator supplying them. */
  inferred: ReadonlySet<string>;
}

export interface MissionQueryPanelProps {
  query: string;
  onQueryChange: (q: string) => void;
  onRun: () => void;
  running: boolean;
  parameters: MissionParameters;
  aoiValidation: ValidationResult;
  /** Non-null blocks the run and explains why. */
  blockedReason: string | null;
}

const EXAMPLE =
  "Show flood-affected areas around Nagaon, Assam between the latest Sentinel-1 " +
  "observation and the permanent-water baseline.";

export function MissionQueryPanel({
  query,
  onQueryChange,
  onRun,
  running,
  parameters,
  aoiValidation,
  blockedReason,
}: MissionQueryPanelProps) {
  const fieldId = useId();
  const [touched, setTouched] = useState(false);

  const empty = query.trim().length === 0;
  const blocked = blockedReason ?? (empty ? "Enter a mission query." : null);

  return (
    <Panel title="Mission">
      <PanelSection>
        <label htmlFor={fieldId} className="label" style={{ display: "block" }}>
          Query
        </label>
        <textarea
          id={fieldId}
          className="field"
          rows={4}
          value={query}
          placeholder={EXAMPLE}
          spellCheck={false}
          onChange={(e) => onQueryChange(e.target.value)}
          onBlur={() => setTouched(true)}
          aria-describedby={blocked && touched ? `${fieldId}-err` : undefined}
          aria-invalid={Boolean(blocked) && touched}
          style={{ marginTop: 6 }}
        />
        {blocked && touched ? (
          <p
            id={`${fieldId}-err`}
            className="mono sig"
            role="alert"
            style={{ fontSize: 10, margin: "6px 0 0" }}
          >
            {blocked}
          </p>
        ) : null}
      </PanelSection>

      <PanelSection title="Resolved parameters">
        <Param
          label="AOI"
          value={parameters.aoiName}
          inferred={parameters.inferred.has("aoiName")}
          reason="No AOI has been drawn or named."
        />
        <Readout
          label="Area"
          value={
            parameters.aoiAreaSqM === null ? null : formatArea(parameters.aoiAreaSqM)
          }
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
      </PanelSection>

      {!aoiValidation.valid && aoiValidation.findings.length > 0 ? (
        <PanelSection title="AOI blocks this run">
          {aoiValidation.findings
            .filter((f) => f.severity === "error")
            .map((f) => (
              <p
                key={f.rule}
                className="mono sig"
                style={{ fontSize: 10, margin: "0 0 5px", lineHeight: 1.45 }}
              >
                ✕ {f.message}
              </p>
            ))}
        </PanelSection>
      ) : null}

      <div style={{ padding: 10 }}>
        <button
          className="btn btn-primary"
          style={{ width: "100%", height: 32 }}
          onClick={onRun}
          disabled={running || Boolean(blocked) || !aoiValidation.valid}
        >
          {running ? "Running…" : "Run analysis"}
        </button>
      </div>
    </Panel>
  );
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
