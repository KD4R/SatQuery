"use client";

/**
 * The agent-activity feed behind the toasts (P5 §2C, P2-16).
 *
 * Demo replays the pinned narratives on the same schedule as the run script — no
 * socket, deterministic for Playwright. Live opens the gateway mission socket, but
 * only once the run is going and a token exists (a socket without a token can only
 * be refused), and forwards exactly what the orchestrator emitted.
 *
 * Extracted from the console so the canonical dashboard and any future surface
 * share one implementation instead of each growing its own timer logic.
 */

import { useEffect, useMemo, useState } from "react";

import { DEMO_AGENT_EVENTS, demoEventAt } from "./fixtures";
import { hasAccessToken } from "./api/gateway";
import { useMissionEvents, type AgentEvent } from "./ws/useMissionEvents";
import type { RunPhase } from "./useMissionRun";

export interface AgentActivity {
  events: AgentEvent[];
  dismiss: (id: string) => void;
}

export function useAgentActivity(
  demo: boolean,
  run: { phase: RunPhase; missionId: string | null; jobId: string | null },
): AgentActivity {
  const [demoEventTick, setDemoEventTick] = useState(0);
  const [demoDismissed, setDemoDismissed] = useState<ReadonlySet<string>>(new Set());

  useEffect(() => {
    if (!demo || run.phase !== "running") return;
    setDemoEventTick(0); // a re-run replays the feed from the top
    setDemoDismissed(new Set());
    const timers: ReturnType<typeof setTimeout>[] = [];
    DEMO_AGENT_EVENTS.forEach((e, i) => {
      timers.push(setTimeout(() => setDemoEventTick(i + 1), e.atMs));
    });
    return () => timers.forEach(clearTimeout);
  }, [demo, run.phase]);

  const demoEvents = useMemo(
    () =>
      DEMO_AGENT_EVENTS.slice(0, demoEventTick)
        .map(demoEventAt)
        .filter((e) => !demoDismissed.has(e.id)),
    [demoEventTick, demoDismissed],
  );

  const live = useMissionEvents(
    demo ? null : (run.missionId ?? run.jobId ?? null),
    !demo && run.phase === "running" && hasAccessToken(),
  );

  return {
    events: demo ? demoEvents : live.events,
    dismiss: demo
      ? (id: string) => setDemoDismissed((prev) => new Set(prev).add(id))
      : live.dismiss,
  };
}
