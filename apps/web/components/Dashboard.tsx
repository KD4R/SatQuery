"use client";
import {
  Download,
  FileText,
  Globe2,
  Menu,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import MapCanvas from "./MapCanvas";
import QueryConsole from "./QueryConsole";
import EvidencePanel from "./EvidencePanel";
import ConfidenceCard from "./ConfidenceCard";
import RunTimeline from "./RunTimeline";
import SensorCard from "./SensorCard";
import MonitoringCard from "./MonitoringCard";
import ReportCard from "./ReportCard";
import TraceDrawer from "./TraceDrawer";
import type { MissionState, Stage } from "../lib/types";
const initialQuery =
  "Show me the flooded areas around Guntur and explain why you chose SAR.";
const stages: Stage[] = [
  {
    key: "PARSE",
    label: "Mission plan validated",
    detail:
      "Natural-language intent normalized into a bounded geospatial task.",
    status: "done",
    time: "11:39",
  },
  {
    key: "RESOLVE",
    label: "AOI resolved",
    detail: "Guntur District → validated polygon and coordinate reference.",
    status: "done",
    time: "11:39",
  },
  {
    key: "DISCOVER",
    label: "Observations discovered",
    detail: "3 candidate scenes matched the spatial + temporal constraints.",
    status: "done",
    time: "11:40",
  },
  {
    key: "ROUTE",
    label: "SAR selected",
    detail: "67% optical cloud cover crossed the quality gate for this AOI.",
    status: "done",
    time: "11:40",
  },
  {
    key: "EXECUTE",
    label: "Geo analysis complete",
    detail:
      "Change mask measured from the selected observation with provenance.",
    status: "done",
    time: "11:42",
  },
  {
    key: "EXPLAIN",
    label: "Evidence chain verified",
    detail:
      "Headline values linked to source observations and processing metadata.",
    status: "done",
    time: "11:42",
  },
];
const evidence = [
  {
    id: "e1",
    kind: "observation",
    title: "Sentinel-1 acquisition",
    source: "P4 · EO/Data",
    detail: "Cloud-robust scene selected after optical quality gate.",
    status: "verified" as const,
    provenance: "dataset S1-Guntur-2026-09-18 · processing v1.4",
  },
  {
    id: "e2",
    kind: "decision",
    title: "SAR route rationale",
    source: "P2 · Mission",
    detail: "AOI-level cloud fraction is 67%; SAR remains usable under cloud.",
    status: "verified" as const,
    provenance: "run SAT-2409 · decision node ROUTE",
  },
  {
    id: "e3",
    kind: "measurement",
    title: "Flood extent measurement",
    source: "P3 · Geo inference",
    detail: "18.7 ha change polygon with radar-shadow exclusion.",
    status: "supporting" as const,
    provenance: "model v2.1 · CRS EPSG:32644",
  },
];
export default function Dashboard() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [active, setActive] = useState("mission");
  const [query, setQuery] = useState(initialQuery);
  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [rightRail, setRightRail] = useState(true);
  const [mission, setMission] = useState<MissionState>({
    missionId: "MIS-2409",
    runId: "SAT-2409",
    status: "completed",
    query: initialQuery,
    location: "Guntur District · Andhra Pradesh",
    aoiArea: "2,184 km²",
    confidence: 0.91,
    stages,
    observations: [],
    evidence,
    decision: {
      winner: "SAR",
      reason: "67% cloud cover over the selected AOI",
      optical: "67% cloud",
      sar: "Ready",
    },
    summary: "18.7 ha newly inundated",
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("satquery-theme", theme);
  }, [theme]);
  useEffect(() => {
    const saved = localStorage.getItem("satquery-theme") as
      | "dark"
      | "light"
      | null;
    if (saved) setTheme(saved);
  }, []);
  const run = () => {
    if (running || !query.trim()) return;
    setRunning(true);
    setMission((m) => ({
      ...m,
      status: "running",
      query,
      stages: m.stages.map((s, i) =>
        i === 4 ? { ...s, status: "active" } : s,
      ),
    }));
    setTimeout(() => {
      setMission((m) => ({
        ...m,
        status: "completed",
        confidence: 0.91,
        stages: m.stages.map((s) => ({ ...s, status: "done" })),
      }));
      setRunning(false);
    }, 1400);
  };
  const reset = () => {
    setQuery(initialQuery);
    setMission((m) => ({
      ...m,
      status: "completed",
      confidence: 0.91,
      stages,
    }));
  };
  const contentTitle =
    active === "mission"
      ? "Mission overview"
      : active === "map"
        ? "Map workspace"
        : active === "monitor"
          ? "Persistent monitoring"
          : active === "evidence"
            ? "Evidence chain"
            : active === "history"
              ? "Mission history"
              : "Reports & decision briefs";
  return (
    <div className="app-shell">
      <div className={`mobile-nav ${mobileNav ? "open" : ""}`}>
        <Sidebar
          active={active}
          onSelect={(id) => {
            setActive(id);
            setMobileNav(false);
          }}
        />
      </div>
      <div className="desktop-sidebar">
        <Sidebar active={active} onSelect={setActive} />
      </div>
      <main className="main">
        <Topbar
          theme={theme}
          onTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          runId={mission.runId}
        />
        <div className="mobile-top">
          <button className="icon-btn" onClick={() => setMobileNav(true)}>
            <Menu size={17} />
          </button>
          <span>{contentTitle}</span>
        </div>
        <div className="content">
          <div className="page-head">
            <div>
              <div className="eyebrow">FLAGSHIP MISSION · FLOOD IMPACT</div>
              <h1>
                See what changed.
                <br />
                <span>Know why.</span>
              </h1>
              <p className="subtitle">
                A map-first command center for evidence-backed satellite
                intelligence. Plan the mission, inspect observations, arbitrate
                sensors, measure change, and keep every conclusion auditable.
              </p>
            </div>
            <div className="head-actions">
              <span className="gateway-chip">
                <i /> Gateway only · secured
              </span>
              <button className="primary-btn" onClick={reset}>
                <RefreshCw size={14} /> New mission
              </button>
            </div>
          </div>
          <div className="workspace-mode">
            <div>
              <b>{contentTitle}</b>
              <span>
                {active === "mission"
                  ? "Flagship flood mission and evidence-first workflow"
                  : active === "map"
                    ? "Inspect AOI, observations, overlays and confidence layers"
                    : active === "monitor"
                      ? "Recurring acquisition, alerting and mission watch state"
                      : active === "evidence"
                        ? "Provenance, observations, model metadata and audit trace"
                        : active === "history"
                          ? "Temporal mission memory and prior runs"
                          : "Decision briefs, report generation and export surfaces"}
              </span>
            </div>
            <span className="mono-chip">P5 / {active.toUpperCase()}</span>
          </div>
          <div className="workspace">
            <div className="map-card">
              <MapCanvas />
            </div>
            {rightRail && (
              <div className="right-rail">
                <QueryConsole
                  value={query}
                  onChange={setQuery}
                  onRun={run}
                  running={running}
                  onReset={reset}
                />
                <ConfidenceCard confidence={mission.confidence} />
                <EvidencePanel
                  evidence={mission.evidence}
                  onTrace={() => setTrace(true)}
                />
              </div>
            )}
            <button
              className="rail-toggle"
              onClick={() => setRightRail(!rightRail)}
              title={rightRail ? "Hide analysis rail" : "Show analysis rail"}
            >
              {rightRail ? (
                <PanelRightClose size={15} />
              ) : (
                <PanelRightOpen size={15} />
              )}
            </button>
          </div>
          <div className="section-strip">
            <div>
              <span>MISSION ID</span>
              <b>{mission.missionId}</b>
            </div>
            <div>
              <span>AOI</span>
              <b>{mission.location}</b>
            </div>
            <div>
              <span>RESULT</span>
              <b>{mission.summary}</b>
            </div>
            <div>
              <span>CONFIDENCE</span>
              <b>
                {mission.confidence
                  ? `${Math.round(mission.confidence * 100)}%`
                  : "—"}
              </b>
            </div>
            <div>
              <span>STATUS</span>
              <b className="success-text">
                {mission.status === "running" ? "RUNNING" : "EVIDENCE READY"}
              </b>
            </div>
          </div>
          <div className="bottom-grid">
            <RunTimeline stages={mission.stages} />
            <SensorCard />
            <MonitoringCard />
            <ReportCard onReport={() => setActive("reports")} />
          </div>
          <footer className="app-footer">
            <div>
              <Globe2 size={14} />
              <b>SatQuery AI</b>
              <span>Evidence-first satellite intelligence</span>
            </div>
            <div>
              <span>Gateway-only browser access</span>
              <span>•</span>
              <span>Traceable outputs</span>
              <span>•</span>
              <span>Accessible UI</span>
            </div>
          </footer>
        </div>
      </main>
      {trace && (
        <TraceDrawer
          stages={mission.stages}
          runId={mission.runId}
          onClose={() => setTrace(false)}
        />
      )}
      <div className="mobile-nav-overlay" onClick={() => setMobileNav(false)} />
    </div>
  );
}
