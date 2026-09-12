import { CircleCheck, Clock3, LoaderCircle, OctagonAlert } from "lucide-react";
import type { Stage } from "../lib/types";
export default function RunTimeline({ stages }: { stages: Stage[] }) {
  return (
    <section className="card timeline-card">
      <div className="card-head">
        <div>
          <div className="card-title">MISSION RUN</div>
          <div className="card-sub">Auditable execution trace</div>
        </div>
        <span className="mono-chip">LIVE TRACE</span>
      </div>
      <div className="timeline">
        {stages.map((s, i) => (
          <div className={`timeline-row ${s.status}`} key={s.key}>
            <div className="timeline-icon">
              {s.status === "done" ? (
                <CircleCheck size={14} />
              ) : s.status === "active" ? (
                <LoaderCircle className="spin" size={14} />
              ) : s.status === "warning" ? (
                <OctagonAlert size={14} />
              ) : (
                <Clock3 size={14} />
              )}
            </div>
            <div>
              <strong>{s.label}</strong>
              <span>{s.detail}</span>
            </div>
            <b className="timeline-time">{s.time || "—"}</b>
            {i < stages.length - 1 && <i className="timeline-line" />}
          </div>
        ))}
      </div>
    </section>
  );
}
