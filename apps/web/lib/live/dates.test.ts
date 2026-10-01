import { describe, expect, it } from "vitest";

import { dateRangeProblem, describeRange, matchingPreset, presetRange, rangeDays, toTemporalWindow } from "./dates";

const TODAY = new Date("2026-10-01T12:00:00Z");

describe("When step (dates)", () => {
  it("presets end today and go back N days", () => {
    expect(presetRange(30, TODAY)).toEqual({ start: "2026-09-01", end: "2026-10-01" });
    expect(matchingPreset(presetRange(7, TODAY), TODAY)).toBe(7);
    expect(matchingPreset({ start: "2024-07-01", end: "2024-07-15" }, TODAY)).toBeNull();
  });

  it("validates ranges in words", () => {
    expect(dateRangeProblem(null, TODAY)).toBeNull();
    expect(dateRangeProblem({ start: "2024-07-01", end: "" }, TODAY)).toMatch(/both dates/);
    expect(dateRangeProblem({ start: "2024-07-15", end: "2024-07-01" }, TODAY)).toMatch(/before the end/);
    expect(dateRangeProblem({ start: "2026-09-01", end: "2026-12-01" }, TODAY)).toMatch(/future/);
  });

  it("sends whole days as instants, or nothing for automatic", () => {
    expect(toTemporalWindow({ start: "2024-07-01", end: "2024-07-15" })).toEqual({
      start: "2024-07-01T00:00:00Z",
      end: "2024-07-15T23:59:59Z",
    });
    expect(toTemporalWindow(null)).toBeNull();
    expect(rangeDays({ start: "2024-07-01", end: "2024-07-15" })).toBe(15);
    expect(describeRange(null)).toMatch(/Automatic/);
    expect(describeRange({ start: "2024-07-01", end: "2024-07-15" })).toBe("1 Jul 2024 → 15 Jul 2024 · 15 days");
  });
});
