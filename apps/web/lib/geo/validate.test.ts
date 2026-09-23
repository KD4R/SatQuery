/**
 * P5-06: test_aoi_draw_edit_and_validation_ux_valid()
 *                     / ..._invalid_input()
 */
import { describe, expect, it } from "vitest";

import { MAX_AREA_SQ_KM, validateAOI } from "./validate";
import type { GeoJSONPolygon } from "../api/types";

/** ~0.5° box near Guntur: a realistic, valid AOI. */
const GOOD: GeoJSONPolygon = {
  type: "Polygon",
  coordinates: [
    [
      [80.3, 16.2],
      [80.8, 16.2],
      [80.8, 16.6],
      [80.3, 16.6],
      [80.3, 16.2],
    ],
  ],
};

describe("validateAOI — accepts", () => {
  it("a well-formed polygon, and measures it", () => {
    const r = validateAOI(GOOD);
    expect(r.valid).toBe(true);
    expect(r.findings.filter((f) => f.severity === "error")).toEqual([]);
    expect(r.areaSqM).not.toBeNull();
    // ~0.5° x 0.4° at 16°N is roughly 2,300 km². Bound loosely; this is a sanity
    // check on the units (m², not km²), not on turf's accuracy.
    expect(r.areaSqM! / 1e6).toBeGreaterThan(1_000);
    expect(r.areaSqM! / 1e6).toBeLessThan(4_000);
  });
});

describe("validateAOI — refuses", () => {
  it("nothing drawn", () => {
    const r = validateAOI(null);
    expect(r.valid).toBe(false);
    expect(r.findings[0]?.rule).toBe("aoi.missing");
  });

  it("too few corners", () => {
    const r = validateAOI({
      type: "Polygon",
      coordinates: [[[80, 16], [81, 16], [80, 16]]],
    });
    expect(r.valid).toBe(false);
    expect(r.findings.map((f) => f.rule)).toContain("aoi.vertices");
  });

  it("an out-of-range coordinate", () => {
    const r = validateAOI({
      type: "Polygon",
      coordinates: [[[80, 16], [999, 16], [80.8, 16.6], [80, 16]]],
    });
    expect(r.valid).toBe(false);
    expect(r.findings.map((f) => f.rule)).toContain("aoi.bounds");
  });

  it("a bowtie that crosses itself", () => {
    const r = validateAOI({
      type: "Polygon",
      coordinates: [
        [
          [80.0, 16.0],
          [81.0, 17.0],
          [81.0, 16.0],
          [80.0, 17.0],
          [80.0, 16.0],
        ],
      ],
    });
    expect(r.valid).toBe(false);
    expect(r.findings.map((f) => f.rule)).toContain("aoi.selfIntersects");
  });

  it("an AOI larger than the analysis budget allows", () => {
    const r = validateAOI({
      type: "Polygon",
      coordinates: [
        [
          [60, 0],
          [100, 0],
          [100, 30],
          [60, 30],
          [60, 0],
        ],
      ],
    });
    expect(r.valid).toBe(false);
    const finding = r.findings.find((f) => f.rule === "aoi.tooLarge");
    expect(finding).toBeDefined();
    // The message must name the limit, or the operator cannot act on it.
    expect(finding!.message).toContain(MAX_AREA_SQ_KM.toLocaleString());
  });

  it("an AOI smaller than the sensor can resolve", () => {
    const r = validateAOI({
      type: "Polygon",
      coordinates: [
        [
          [80.3000, 16.2000],
          [80.3005, 16.2000],
          [80.3005, 16.2005],
          [80.3000, 16.2005],
          [80.3000, 16.2000],
        ],
      ],
    });
    expect(r.valid).toBe(false);
    expect(r.findings.map((f) => f.rule)).toContain("aoi.tooSmall");
  });

  it("an AOI crossing the antimeridian", () => {
    const r = validateAOI({
      type: "Polygon",
      coordinates: [
        [
          [170, 10],
          [-170, 10],
          [-170, 20],
          [170, 20],
          [170, 10],
        ],
      ],
    });
    expect(r.valid).toBe(false);
    expect(r.findings.map((f) => f.rule)).toContain("aoi.antimeridian");
  });
});

describe("validateAOI — warns without blocking", () => {
  it("on an unclosed ring, because the draw tool closes it on completion", () => {
    const r = validateAOI({
      type: "Polygon",
      coordinates: [[[80.3, 16.2], [80.8, 16.2], [80.8, 16.6], [80.3, 16.6]]],
    });
    const unclosed = r.findings.find((f) => f.rule === "aoi.unclosed");
    expect(unclosed?.severity).toBe("warning");
    expect(r.valid).toBe(true);
  });
});
