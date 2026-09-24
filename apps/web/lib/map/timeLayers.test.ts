import { describe, expect, it } from "vitest";

import { ASSAM_SCENARIO } from "../fixtures/assam";
import { buildTimeMachine, epochOpacities } from "./timeLayers";

describe("buildTimeMachine", () => {
  it("builds before → after → change from the fixture overlays", () => {
    const model = buildTimeMachine(ASSAM_SCENARIO);
    expect(model).not.toBeNull();
    expect(model!.epochs.map((e) => e.id)).toEqual([
      "tm-baseline",
      "tm-observed",
      "tm-change",
    ]);
    expect(model!.epochs.map((e) => e.label)).toEqual([
      "Before",
      "After",
      "Change",
    ]);
    // The fixture's own honesty: Sen1Floods11 publishes no per-chip timestamp,
    // so every date on the scrubber must be null rather than plausible.
    expect(model!.epochs[0]!.acquired).toBeNull();
    expect(model!.epochs[1]!.acquired).toBeNull();
  });

  it("opens on the observed scene and reports the rail as undated", () => {
    const model = buildTimeMachine(ASSAM_SCENARIO);
    expect(model!.initialIndex).toBe(1);
    expect(model!.hasDates).toBe(false);
  });

  it("is a dated rail when the backend supplies acquisition times", () => {
    const dated = {
      ...ASSAM_SCENARIO,
      comparison: {
        ...ASSAM_SCENARIO.comparison,
        before: {
          ...ASSAM_SCENARIO.comparison.before!,
          acquired: "2025-01-01T00:00:00.000Z",
        },
        after: {
          ...ASSAM_SCENARIO.comparison.after,
          acquired: "2025-02-01T00:00:00.000Z",
        },
      },
    };
    const model = buildTimeMachine(dated);
    expect(model!.hasDates).toBe(true);
    // Dates belong to the scene epochs; the derived change map stays undated.
    expect(model!.epochs[2]!.acquired).toBeNull();
  });

  it("refuses a scrubber over fewer than two temporal states", () => {
    const single = {
      ...ASSAM_SCENARIO,
      overlays: { observed: ASSAM_SCENARIO.overlays["observed"]! },
    };
    expect(buildTimeMachine(single)).toBeNull();
  });
});

describe("epochOpacities", () => {
  const model = buildTimeMachine(ASSAM_SCENARIO)!;

  it("gives the active epoch its paint opacity and everything else 0", () => {
    expect(epochOpacities(model, 0)).toEqual({
      "tm-baseline": 1,
      "tm-observed": 0,
      "tm-change": 0,
    });
    expect(epochOpacities(model, 2)).toEqual({
      "tm-baseline": 0,
      "tm-observed": 0,
      "tm-change": 0.92,
    });
  });

  it("clamps an out-of-range index instead of producing NaN opacities", () => {
    expect(epochOpacities(model, -3)).toEqual(epochOpacities(model, 0));
    expect(epochOpacities(model, 9)).toEqual(epochOpacities(model, 2));
  });
});
