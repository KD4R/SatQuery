"use client";

import Link from "next/link";
import { FileText } from "lucide-react";

import { reportRoute } from "../lib/nav";

/**
 * Entry point to report generation (P5-14).
 *
 * The card used to print a finished-looking brief ("18.7 ha newly inundated",
 * "0.91 IoU") before any run had happened. A brief that exists before its analysis
 * is the most dangerous kind of fake progress on this product, so the card now
 * carries no figures at all: it links to the report screen once a run has produced
 * a mission to report on, and says why it cannot before that.
 */
export default function ReportCard({
  missionId,
}: {
  /** Set once a run has completed; null keeps the action disabled. */
  missionId: string | null;
}) {
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
      </div>
      <div className="brief">
        <div className="brief-kicker">
          {missionId ? "REPORT AVAILABLE" : "NO REPORT YET"}
        </div>
        <p>
          {missionId
            ? "Report generation is asynchronous: the report screen submits a job and renders the result when it completes, with its caveats attached."
            : "Complete a run first. A report is generated from a finished mission, never previewed ahead of its analysis."}
        </p>
      </div>
      <div className="report-actions">
        {missionId ? (
          <Link className="ghost-btn" href={reportRoute(missionId)}>
            <FileText size={13} /> Open report
          </Link>
        ) : (
          <button className="ghost-btn" disabled title="Complete a run first.">
            <FileText size={13} /> Open report
          </button>
        )}
      </div>
    </section>
  );
}
