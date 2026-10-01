import { describe, expect, it } from "vitest";

import { parseNominatim, rectanglePolygon } from "./geocode";
import { validateAOI } from "./validate";

describe("place search parsing (audit F4)", () => {
  it("turns Nominatim's [south, north, west, east] box into [w, s, e, n]", () => {
    const [r] = parseNominatim([
      { display_name: "Nagaon, Assam, India", lat: "26.35", lon: "92.68", boundingbox: ["26.25", "26.48", "92.55", "92.85"], type: "city" },
    ]);
    expect(r!.bbox).toEqual([92.55, 26.25, 92.85, 26.48]);
    expect(r!.center).toEqual([92.68, 26.35]);
  });

  it("drops malformed rows instead of guessing", () => {
    expect(parseNominatim([{ display_name: "x", lat: "a", lon: "b", boundingbox: [] }, null, 3])).toEqual([]);
    expect(parseNominatim({})).toEqual([]);
  });
});

describe("rectangle AOI", () => {
  it("is a closed, valid polygon whichever corners are clicked", () => {
    const p = rectanglePolygon([92.8, 26.45], [92.6, 26.3]);
    expect(p.coordinates[0]![0]).toEqual([92.6, 26.3]);
    expect(p.coordinates[0]![4]).toEqual([92.6, 26.3]);
    expect(validateAOI(p).valid).toBe(true);
  });
});

import { aoiForPlace, bboxAreaKm2 } from "./geocode";

describe("place → AOI", () => {
  const place = (bbox: [number, number, number, number]) => ({
    name: "Somewhere, Assam, India",
    bbox,
    center: [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2] as [number, number],
    kind: "city",
  });

  it("uses a town's own box when it fits the limit", () => {
    const r = aoiForPlace(place([92.6, 26.3, 92.8, 26.45]));
    expect(r.note).toBeNull();
    expect(validateAOI(r.polygon).valid).toBe(true);
  });

  it("replaces a state-sized box with a 30 km box and says so", () => {
    const big = place([89.7, 24.1, 96.0, 28.0]);
    expect(bboxAreaKm2(big.bbox)).toBeGreaterThan(2500);
    const r = aoiForPlace(big);
    expect(r.note).toMatch(/larger than the 2,500 km²/);
    expect(validateAOI(r.polygon).valid).toBe(true);
    expect(validateAOI(r.polygon).areaSqM! / 1e6).toBeGreaterThan(800);
  });

  it("gives a point-like result a 10 km box", () => {
    const r = aoiForPlace(place([92.7, 26.35, 92.701, 26.351]));
    expect(r.note).toMatch(/10 km box/);
    expect(validateAOI(r.polygon).valid).toBe(true);
  });
});
