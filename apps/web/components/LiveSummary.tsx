import { FileText } from "lucide-react";

import { confidenceBand } from "../lib/geo/format";
import type { MissionState } from "../lib/api/types";

/**
 * The agent's synthesised answer for a live run, with the gate applied in the UI
 * as well as in the backend.
 *
 * Two honesty rules are enforced here rather than trusted:
 *   - Below the LOW band the summary is withheld. Low confidence must never
 *     become confident prose, and the agent's prose is written without regard to
 *     the score it is attached to.
 *   - Sensors and citations are listed exactly as published; an absent field says
 *     so instead of being omitted.
 */
export default function LiveSummary({ state }: { state: MissionState }) {
  const score = state.confidence_score;
  const band = typeof score === "number" ? confidenceBand(score) : null;
  const out = state.synthesized_output ?? null;
  const summary = out && typeof out.summary === "string" ? out.summary : null;
  const citations = Array.isArray(out?.citations) ? (out.citations as unknown[]).length : null;
  const sensors = state.selected_sensors ?? [];

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <div className="title-row">
            <FileText size={14} />
            <div className="card-title">AGENT SUMMARY</div>
          </div>
          <div className="card-sub">Written from the evidence graph, gated on confidence</div>
        </div>
      </div>

      {band === "LOW" ? (
        <p className="evidence-detail" role="status">
          Withheld: confidence is low, so no conclusion is stated. See the
          uncertainty reasons and the evidence chain.
        </p>
      ) : summary ? (
        <p className="evidence-detail">{summary}</p>
      ) : (
        <p className="evidence-detail">
          NOT AVAILABLE — the agent published no summary for this run.
        </p>
      )}

      <div className="basis-row">
        <span>Sensors selected</span>
        <b>{sensors.length ? sensors.join(" · ") : "NOT AVAILABLE"}</b>
      </div>
      <div className="basis-row">
        <span>Evidence citations</span>
        <b>{citations === null ? "NOT AVAILABLE" : citations}</b>
      </div>
    </section>
  );
}
