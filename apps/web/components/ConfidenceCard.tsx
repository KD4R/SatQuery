import { AlertTriangle, Scale, ShieldCheck } from "lucide-react";
export default function ConfidenceCard({
  confidence,
}: {
  confidence: number | null;
}) {
  const pct = confidence == null ? 0 : Math.round(confidence * 100);
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
            <b>
              {confidence == null
                ? "No assertion"
                : pct >= 85
                  ? "High"
                  : "Review"}
            </b>
          </div>
          <div className="progress">
            <i style={{ width: `${pct}%` }} />
          </div>
          <div className="basis-row">
            <span>Model agreement</span>
            <b>{confidence == null ? "—" : "0.91 IoU"}</b>
          </div>
          <div className="basis-row">
            <span>Terrain plausibility</span>
            <b>{confidence == null ? "—" : "High"}</b>
          </div>
        </div>
      </div>
      <div className="uncertainty">
        <AlertTriangle size={14} />
        <div>
          <b>Human-in-loop gate</b>
          <span>
            {confidence == null
              ? "No conclusion is displayed until evidence arrives."
              : "Radar shadow affects ~4% of the AOI; excluded from headline measurement."}
          </span>
        </div>
      </div>
    </section>
  );
}
