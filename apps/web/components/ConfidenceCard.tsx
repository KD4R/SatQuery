import { AlertTriangle, ShieldCheck } from "lucide-react";

import { confidenceBand } from "../lib/geo/format";

/**
 * Confidence and uncertainty for a live run (P5-11).
 *
 * Only what the agent published is shown: the score, its band, and the named
 * uncertainty reasons. There are deliberately no "model agreement" or "terrain
 * plausibility" rows — the agent does not publish them, and a row with a plausible
 * value that nobody computed is exactly the failure this card exists to prevent.
 * Low confidence never becomes reassuring prose: the note under the score says a
 * human should look, and the summary is withheld upstream.
 */
export default function ConfidenceCard({
  confidence,
  reasons = [],
}: {
  confidence: number | null;
  /** The agent's own uncertainty_reasons; empty means it published none. */
  reasons?: string[];
}) {
  const pct = confidence == null ? 0 : Math.round(confidence * 100);
  const band = confidence == null ? null : confidenceBand(confidence);

  return (
    <section className="card confidence-card">
      <div className="card-head">
        <div>
          <div className="title-row">
            <ShieldCheck size={14} />
            <div className="card-title">CONFIDENCE / UNCERTAINTY</div>
          </div>
          <div className="card-sub">Basis is explicit — never decorative</div>
        </div>
      </div>
      <div className="confidence-main">
        <div
          className="confidence-ring"
          style={{ "--p": `${pct}%` } as React.CSSProperties}
        >
          <span>{confidence == null ? "—" : `${pct}%`}</span>
        </div>
        <div className="confidence-copy">
          <div className="confidence-label">
            {confidence == null ? "Awaiting analysis" : "Composite confidence"}{" "}
            <b>{band ?? "No assertion"}</b>
          </div>
          <div className="progress">
            <i style={{ width: `${pct}%` }} />
          </div>
          {confidence !== null && reasons.length === 0 ? (
            <div className="basis-row">
              <span>Uncertainty reasons</span>
              <b title="The agent published no uncertainty_reasons for this run.">
                NOT AVAILABLE
              </b>
            </div>
          ) : null}
          {reasons.map((r) => (
            <div className="basis-row" key={r}>
              <span>{r}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="uncertainty">
        <AlertTriangle size={14} />
        <div>
          <b>Human-in-loop gate</b>
          <span>
            {confidence == null
              ? "No conclusion is displayed until evidence arrives."
              : band === "LOW"
                ? "Confidence is low. No conclusion is asserted — review the uncertainty reasons before acting."
                : band === "MODERATE"
                  ? "Confidence is moderate. Treat the result as indicative and check the evidence chain."
                  : "Confidence is high. The evidence chain below still lists what supports it."}
          </span>
        </div>
      </div>
    </section>
  );
}
