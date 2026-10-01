"use client";

/**
 * The dashboard's page-bottom telemetry: the small subset of the old top bar
 * (UTC clock · gateway reachability · system state) rendered as a quiet
 * footer line. In demo mode the clock freezes and ENV reads DEMO, same
 * honesty rules as everywhere else. Pass `run` on pages that own a run.
 */

import { useEffect, useState } from "react";

import { getHealth } from "../lib/api/client";
import { demoModeEnabled, type DataSource } from "../lib/api/source";
import type { MissionRun } from "../lib/useMissionRun";
import { utcClock } from "./shell/utcClock";

export default function PageTelemetry({
  run = null,
}: {
  run?: Pick<MissionRun, "phase" | "jobId" | "agentState"> | null;
}) {
  const [gatewayUp, setGatewayUp] = useState<boolean | null>(null);
  const [clock, setClock] = useState("--:--:--");
  const demo = demoModeEnabled();

  useEffect(() => {
    let live = true;
    const controller = new AbortController();
    getHealth(controller.signal)
      .then(() => live && setGatewayUp(true))
      .catch(() => live && setGatewayUp(false));
    return () => {
      live = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (demo) {
      setClock("05:42:00");
      return;
    }
    const tick = () => setClock(utcClock(new Date()));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [demo]);

  const state =
    run?.phase === "running"
      ? "PROCESSING"
      : run?.phase === "failed"
        ? "FAILED"
        : run?.phase === "complete"
          ? "ACTIVE"
          : "IDLE";

  const env: DataSource = demo ? "fixture" : "gateway";

  return (
    <div className="page-telemetry" role="contentinfo" aria-label="System telemetry">
      <span className="pt-item">
        <span className="pt-label">UTC</span>
        <span className="pt-value">{clock}</span>
      </span>
      <span className="pt-sep">·</span>
      <span className="pt-item">
        <span className="pt-label">GATEWAY</span>
        <span
          className={`pt-value ${
            gatewayUp === false ? "pt-warn" : gatewayUp ? "pt-ok" : ""
          }`}
        >
          {gatewayUp === false ? "UNREACHABLE" : gatewayUp ? "REACHABLE" : "CHECKING…"}
        </span>
      </span>
      <span className="pt-sep">·</span>
      <span className="pt-item">
        <span className="pt-label">STATE</span>
        <span
          className={`pt-value ${
            state === "FAILED" ? "pt-warn" : state === "ACTIVE" ? "pt-ok" : state === "PROCESSING" ? "pt-busy" : ""
          }`}
        >
          {state}
        </span>
      </span>
      <span className="pt-sep">·</span>
      <span className="pt-item">
        <span className="pt-label">ENV</span>
        <span className={`pt-value ${env === "fixture" ? "pt-warn" : ""}`}>
          {env === "fixture" ? "DEMO" : "LIVE"}
        </span>
      </span>
    </div>
  );
}
