import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import type { MissionState } from "../api/types";
import { failureHint, km2ToHa, liveStepDetails, toLiveResult } from "./result";

const load = (f: string) =>
  (JSON.parse(readFileSync(join(__dirname, "testdata", f), "utf8")) as { run: MissionState }).run;

describe("MissionState → live result (audit W3, W6, W7, W10)", () => {
  const done = toLiveResult(load("run-completed.json"));

  it("reads the measured area, scene and sensor the agent published", () => {
    expect(done.status).toBe("COMPLETED");
    expect(done.areaKm2).toBeCloseTo(12.345, 3);
    expect(km2ToHa(done.areaKm2!)).toBeCloseTo(1234.5, 1);
    expect(done.scene.id).toBe("S1_NEW_FULL");
    expect(done.scene.sensor).toBe("S1_SAR");
    expect(done.scene.acquiredAt).toMatch(/^2024-07-04/);
  });

  it("keeps an uncalibrated model confidence as null, never a number", () => {
    expect(done.confidence.modelConfidence).toBeNull();
    expect(done.confidence.scoreBasis).toBe("acquisition_quality_only");
    expect(done.confidence.score).toBeCloseTo(0.95, 2);
    const inference = done.evidence.find((e) => e.type === "INFERENCE");
    expect(inference?.confidence).toBeNull();
  });

  it("builds WHY, caveats and the search record from the run", () => {
    expect(done.why.map((w) => w.key)).toEqual(expect.arrayContaining(["sensor_choice", "methodology", "confidence_rationale"]));
    expect(done.caveats.some((c) => c.startsWith("single-date Otsu"))).toBe(true);
    expect(done.caveats.some((c) => c.startsWith("produced by"))).toBe(false);
    expect(done.search?.bbox).toEqual([92.6, 26.3, 92.8, 26.45]);
    expect(done.search?.attempts).toHaveLength(1);
    expect(done.inference.traceId).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("names evidence nodes from their data, not raw ids", () => {
    const titles = done.evidence.map((e) => e.title);
    expect(titles).toContain("S1_SAR scene");
    expect(titles.some((t) => t.startsWith("Water segmentation"))).toBe(true);
  });

  it("a failed run carries its reason and a next step, and no numbers", () => {
    const failed = toLiveResult(load("run-failed.json"));
    expect(failed.status).toBe("FAILED");
    expect(failed.failure?.reason).toBe("NO_SCENES_IN_WINDOW");
    expect(failed.failure?.text).toMatch(/No scenes intersect the AOI/);
    expect(failed.failure?.hint).toMatch(/date range/i);
    expect(failed.areaKm2).toBeNull();
    expect(failed.confidence.score).toBeNull();
  });

  it("describes each step with what actually happened", () => {
    const d = liveStepDetails(load("run-completed.json"));
    expect(d.plan).toBe("Hazard: flood.");
    expect(d.search).toMatch(/5 scene\(s\) in 2024-06-29 → 2024-07-06\. Using S1_NEW_FULL\./);
    expect(d.analyse).toMatch(/12\.35 km² of water measured \(baseline method\)/);
    expect(d.gate).toBe("Score 0.95.");
  });

  it("has a hint for every documented failure reason", () => {
    for (const r of ["AOI_REQUIRED", "AOI_TOO_LARGE", "NO_ANALYSABLE_SCENE", "CATALOGUE_UNAVAILABLE", "LOW_CONFIDENCE", "INFERENCE_UNAVAILABLE"]) {
      expect(failureHint(r)).not.toBe(failureHint("UNKNOWN_CODE"));
    }
  });
});
