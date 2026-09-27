"use client";

/**
 * Step-by-step beginner's guide — how to run a mission on this site, from
 * typing a question to reading the evidence. No fake figures; every pointer
 * describes a control that actually exists on this page.
 */

import { MousePointerClick, PenLine, Play, ListOrdered, FileSearch, BellRing } from "lucide-react";

const STEPS: { icon: React.ReactNode; title: string; body: string }[] = [
  {
    icon: <MousePointerClick size={16} />,
    title: "1 · Ask a question",
    body: "Type what you want to know in the MISSION COPILOT box — plain language is fine. \"Show flood-affected areas near Nagaon between the latest Sentinel-1 pass and the permanent-water baseline\" already works.",
  },
  {
    icon: <PenLine size={16} />,
    title: "2 · Draw or keep the area",
    body: "The map starts on the demo AOI. Use DRAW AOI on the map to outline your own region of interest; the polygon is checked against the analysis budget before anything runs.",
  },
  {
    icon: <Play size={16} />,
    title: "3 · Run the mission",
    body: "Press ENTER (or the run arrow). The MISSION RUN · STEPS list under the query shows each stage the backend reports — the highlighted step is the one being processed right now. Live runs report only what the gateway sends; nothing is invented.",
  },
  {
    icon: <ListOrdered size={16} />,
    title: "4 · Read the steps and metrics",
    body: "When the run completes, the mission stats strip and the evidence panel fill in: what was measured, the confidence, and which sensors were used. A DEGRADED stage means a real limitation (e.g. partial swath coverage) — it is shown, not hidden.",
  },
  {
    icon: <FileSearch size={16} />,
    title: "5 · Inspect the evidence",
    body: "Open WHY? EVIDENCE CHAIN to see why each claim was made, which datasets back it, and what was unavailable. Trace opens the full audit trail. In Evidence you can dig through the complete chain.",
  },
  {
    icon: <BellRing size={16} />,
    title: "6 · Keep watching",
    body: "Monitoring turns one mission into a recurring watch over the same AOI, and Reports bundles the result into a decision brief you can export. The bell icon tracks alerts; the clock at the bottom shows system state.",
  },
];

export default function BeginnerGuide() {
  return (
    <section className="dash-section" aria-label="Step by step guide">
      <div className="dash-section-head">
        <span className="dash-section-index">?</span>
        <h2>Step by step guide</h2>
      </div>
      <div className="guide-grid">
        {STEPS.map((s) => (
          <div className="guide-card" key={s.title}>
            <div className="guide-icon">{s.icon}</div>
            <b>{s.title}</b>
            <p>{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
