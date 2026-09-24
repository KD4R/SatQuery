import type { MissionState as BackendMissionState } from "./api/types";
import type { MissionState as UIMissionState, Stage, Evidence, MissionDecision } from "./types";
import type { RunStageView } from "./useMissionRun";

export function toUIStages(runStages: RunStageView[]): Stage[] {
  return runStages.map((rs) => {
    let status: "done" | "active" | "error" | "pending" = "pending";
    if (rs.state === "completed") status = "done";
    else if (rs.state === "running") status = "active";
    else if (rs.state === "failed") status = "error";
    
    return {
      key: rs.key,
      label: rs.label,
      detail: rs.detail,
      status,
    };
  });
}

export function toUIMissionState(
  query: string,
  agentState: BackendMissionState | null,
  runStages: RunStageView[]
): UIMissionState {
  const stages = toUIStages(runStages);

  // Extract evidence from agentState if available
  const evidence: Evidence[] = [];
  if (agentState?.evidence_graph) {
    // nodes is a Record<string, node>, not an array — use Object.values()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const nodesMap = agentState.evidence_graph.nodes as Record<string, any> || {};
    Object.entries(nodesMap).forEach(([id, n]: [string, any], idx: number) => {
      evidence.push({
        id: (n.id as string) || id || `e${idx}`,
        kind: (n.node_type as string) || (n.type as string) || "observation",
        title: (n.label as string) || (n.title as string) || `Evidence ${idx + 1}`,
        source: (n.source as string) || "System",
        detail: (n.detail as string) || (n.summary as string) || "Verified data point.",
        status: typeof n.confidence_score === "number" && n.confidence_score > 0.8 ? "verified" : "supporting",
        provenance: (n.provenance as string) || `trace: ${agentState.trace_id ?? "—"}`,
      });
    });
  }

  // Extract decision if available
  const decision: MissionDecision = {
    winner: "Optical / SAR",
    reason: "Awaiting sensor arbitration...",
    optical: "Pending",
    sar: "Pending"
  };
  
  if (agentState?.selected_sensors && agentState.selected_sensors.length > 0) {
    decision.winner = agentState.selected_sensors.join(", ");
    decision.reason = "Selected by sensor arbitrator";
    decision.optical = agentState.selected_sensors.includes("optical") ? "Selected" : "Omitted";
    decision.sar = agentState.selected_sensors.includes("sar") ? "Selected" : "Omitted";
  }

  return {
    missionId: agentState?.mission_id || "Awaiting submission...",
    runId: agentState?.run_id || "Awaiting run...",
    status: agentState?.status || (runStages.some(s => s.state === 'running') ? 'running' : 'completed'),
    query: agentState?.query || query,
    location: "AOI Target (Resolved from query)",
    aoiArea: agentState?.aoi ? "Polygon resolved" : "Pending",
    confidence: agentState?.confidence_score || 0,
    stages,
    observations: agentState?.observation_ids || [],
    evidence,
    decision,
    summary: agentState?.metadata?.summary || "Mission complete. Evidence assembled.",
    cogUrl: agentState?.metadata?.inference_outcome?.scene_href || agentState?.metadata?.observations?.[0]?.href,
    aoiGeoJson: agentState?.aoi,
  };
}
