import { describe, expect, it } from "vitest";

import { ASSAM_SCENARIO } from "../fixtures";
import { buildEvidenceGraph } from "./graph";

describe("buildEvidenceGraph", () => {
  it("builds a connected chain insight → gate → model from the fixture", () => {
    const g = buildEvidenceGraph(ASSAM_SCENARIO);

    const kinds = new Map(g.nodes.map((n) => [n.id, n.kind]));
    expect(kinds.get(g.rootId)).toBe("insight");
    expect(kinds.get("node-gate")).toBe("gate");
    expect(kinds.get("node-model")).toBe("model");

    const ids = new Set(g.nodes.map((n) => n.id));
    for (const e of g.edges) {
      expect(ids.has(e.source), `edge ${e.id} source ${e.source} exists`).toBe(true);
      expect(ids.has(e.target), `edge ${e.id} target ${e.target} exists`).toBe(true);
    }
  });

  it("carries the fixture's real numbers onto the right nodes", () => {
    const g = buildEvidenceGraph(ASSAM_SCENARIO);

    const insight = g.nodes.find((n) => n.id === g.rootId);
    expect(insight?.value).toContain("3.54");
    expect(insight?.provenance).toContain(ASSAM_SCENARIO.traceId);

    const gate = g.nodes.find((n) => n.kind === "gate");
    expect(gate?.score).toBe(0.87);
    expect(gate?.value).toContain("3"); // three uncertainty factors

    const model = g.nodes.find((n) => n.kind === "model");
    expect(model?.value).toContain("hand-only-v2");

    const s1 = g.nodes.find((n) => n.id === "node-sensor-sentinel-1");
    expect(s1?.score).toBe(0.87);
    const s2 = g.nodes.find((n) => n.id === "node-sensor-sentinel-2");
    expect(s2?.score).toBe(0.42);
  });

  it("marks the primary sensor edge and the gate verdict honestly", () => {
    const g = buildEvidenceGraph(ASSAM_SCENARIO);

    const primaryEdge = g.edges.find((e) => e.target === "node-sensor-sentinel-1");
    expect(primaryEdge?.primary).toBe(true);
    expect(primaryEdge?.label).toBe("primary sensor");

    const corroborating = g.edges.find((e) => e.target === "node-sensor-sentinel-2");
    expect(corroborating?.primary).toBe(false);

    expect(g.passedGate).toBe(true);
  });

  it("keeps a not-available evidence row in the graph instead of dropping it", () => {
    const g = buildEvidenceGraph(ASSAM_SCENARIO);

    // ev-2 (Acquired) has value null — the missing timestamp must stay visible.
    const na = g.nodes.find((n) => n.id === "node-evidence-ev-2");
    expect(na).toBeDefined();
    expect(na?.value).toBeNull();
    expect(na?.reason).toContain("Sen1Floods11");

    const edge = g.edges.find((e) => e.id === "edge-evidence-ev-2");
    expect(edge).toBeDefined();
  });

  it("does not duplicate observation values already carried by sensor nodes", () => {
    const g = buildEvidenceGraph(ASSAM_SCENARIO);
    const values = g.nodes.map((n) => n.value).filter((v): v is string => v !== null);
    expect(new Set(values).size).toBe(values.length);
  });

  it("works when the backend supplies nothing — chain stays connected and honest", () => {
    const empty = {
      ...ASSAM_SCENARIO,
      modelVersion: null,
      evidence: ASSAM_SCENARIO.evidence.map((e) => ({
        ...e,
        value: null,
        provenance: null,
      })),
      arbitration: {
        ...ASSAM_SCENARIO.arbitration,
        readings: [],
        primary: null,
        secondary: null,
      },
      confidence: {
        ...ASSAM_SCENARIO.confidence,
        passedGate: false,
        uncertaintyFactors: [],
      },
    };
    const g = buildEvidenceGraph(empty);

    expect(g.passedGate).toBe(false);
    // insight → gate → model always exist and are wired.
    expect(g.edges.map((e) => e.id)).toContain("edge-insight-gate");
    expect(g.edges.map((e) => e.id)).toContain("edge-gate-model");
    const gate = g.nodes.find((n) => n.kind === "gate");
    expect(gate?.value).toBeNull();
    expect(gate?.reason).toBeDefined();
    const model = g.nodes.find((n) => n.kind === "model");
    expect(model?.value).toBeNull();
  });
});
