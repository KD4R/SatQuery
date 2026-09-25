"use client";
import { Download, FileText, MapPinned, Share2 } from "lucide-react";
import { useState } from "react";
export default function ReportCard({ onReport }: { onReport: () => void }) {
  const [toast, setToast] = useState("");
  const act = (t: string) => {
    setToast(t);
    setTimeout(() => setToast(""), 1800);
  };
  return (
    <section className="card report-card">
      <div className="card-head">
        <div>
          <div className="title-row">
            <FileText size={14} />
            <div className="card-title">DECISION BRIEF</div>
          </div>
          <div className="card-sub">Human-readable, evidence-backed output</div>
        </div>
        <button className="small-icon" onClick={() => act("Link copied")}>
          <Share2 size={13} />
        </button>
      </div>
      <div className="brief">
        <div className="brief-kicker">FLOOD SIGNAL · GUNTUR</div>
        <h3>18.7 ha newly inundated</h3>
        <p>
          Identified within the selected AOI. SAR was selected because optical
          coverage is cloud-limited. Radar shadow is excluded from the headline
          measurement.
        </p>
        <div className="brief-tags">
          <span>0.91 IoU</span>
          <span>18.7 ha</span>
          <span>Provenance attached</span>
        </div>
      </div>
      <div className="report-actions">
        <button className="ghost-btn" onClick={onReport}>
          <FileText size={13} /> View report
        </button>
        <button
          className="ghost-btn"
          onClick={() => act("GeoJSON export prepared")}
        >
          <MapPinned size={13} /> GeoJSON
        </button>
        <button className="ghost-btn" onClick={() => act("Download queued")}>
          <Download size={13} /> Export
        </button>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </section>
  );
}
