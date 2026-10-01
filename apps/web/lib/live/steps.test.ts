import { describe, expect, it } from "vitest";

import { buildLiveSteps, failedStepFor, LIVE_STEPS, statusRank } from "./steps";

describe("live step list (audit W4)", () => {
  it("has one row per agent graph node, in order", () => {
    expect(LIVE_STEPS.map((s) => s.key)).toEqual(["submit", "plan", "sensor", "search", "analyse", "gate", "answer"]);
  });

  it("knows every status the orchestrator persists", () => {
    for (const s of ["INITIALIZED", "PLANNING", "ARBITRATING", "ACQUIRING", "ANALYZING", "GATE_CHECK", "REINVESTIGATE", "COMPLETED"]) {
      expect(statusRank(s)).toBeGreaterThanOrEqual(0);
    }
    expect(statusRank("SOMETHING_NEW")).toBe(-1);
  });

  it("marks finished nodes done and the next one running — nothing more", () => {
    const steps = buildLiveSteps({ furthest: "ARBITRATING", terminal: null });
    expect(steps.map((s) => s.state)).toEqual(["completed", "completed", "completed", "running", "queued", "queued", "queued"]);
  });

  it("a fast run that skipped statuses between polls still counts them done", () => {
    const steps = buildLiveSteps({ furthest: "ANALYZING", terminal: null });
    expect(steps.filter((s) => s.state === "completed")).toHaveLength(5);
  });

  it("a completed run is all green", () => {
    expect(buildLiveSteps({ furthest: "COMPLETED", terminal: "COMPLETED" }).every((s) => s.state === "completed")).toBe(true);
  });

  it("fails the step the reason belongs to and leaves later steps unreached", () => {
    const steps = buildLiveSteps({
      furthest: "ARBITRATING",
      terminal: "FAILED",
      failureReason: "NO_SCENES_IN_WINDOW",
      failureText: "No scenes intersect the AOI.",
    });
    const search = steps.find((s) => s.key === "search")!;
    expect(search.state).toBe("failed");
    expect(search.detail).toBe("No scenes intersect the AOI.");
    expect(steps.find((s) => s.key === "answer")!.state).toBe("queued");
    expect(steps.find((s) => s.key === "sensor")!.state).toBe("completed");
  });

  it("maps reasons to steps", () => {
    expect(failedStepFor("AOI_REQUIRED")).toBe("search");
    expect(failedStepFor("LOW_CONFIDENCE")).toBe("gate");
    expect(failedStepFor("no_separable_threshold")).toBe("analyse");
    expect(failedStepFor(null)).toBeNull();
  });

  it("a transport failure before submit fails the first step", () => {
    const steps = buildLiveSteps({ furthest: null, terminal: null, transportFailed: true, failureText: "down" });
    expect(steps[0]!.state).toBe("failed");
    expect(steps.slice(1).every((s) => s.state === "queued")).toBe(true);
  });
});
