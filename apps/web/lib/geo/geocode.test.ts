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
