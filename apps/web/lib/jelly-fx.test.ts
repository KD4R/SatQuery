import { describe, expect, it } from "vitest";

import {
  chipMorph,
  JELLY_DEFAULTS,
  jellyWobble,
  staggerDelay,
  wobbleSettled,
  withJellyDefaults,
} from "./jelly-fx";

describe("withJellyDefaults", () => {
  it("fills missing params with the documented defaults", () => {
    expect(withJellyDefaults()).toEqual(JELLY_DEFAULTS);
    expect(withJellyDefaults({ swell: 0.5 })).toEqual({
      ...JELLY_DEFAULTS,
      swell: 0.5,
    });
  });

  it("keeps explicitly provided params", () => {
    const p = withJellyDefaults({
      stiffness: 300,
      bounce: 0.5,
      stagger: 10,
    });
    expect(p.stiffness).toBe(300);
    expect(p.bounce).toBe(0.5);
    expect(p.stagger).toBe(10);
  });
});

describe("chipMorph", () => {
  it("scales resting width with label length", () => {
    const short = chipMorph("Off", 12, 12, 32, 6);
    const long = chipMorph("Medium level", 12, 12, 32, 6);
    expect(long.width).toBeGreaterThan(short.width);
    expect(short.height).toBe(32);
    expect(short.fontSize).toBe(12);
  });

  it("clamps tiny labels to a minimum sliver-free unit", () => {
    const one = chipMorph("A", 12, 12, 32, 6);
    const three = chipMorph("Off", 12, 12, 32, 6);
    expect(one.width).toBe(three.width);
  });

  it("gives the active chip a label-proportional share of the barge", () => {
    const small = chipMorph("List", 12, 12, 32, 14);
    const big = chipMorph("OBSERVE · PREPROCESS", 12, 12, 32, 14);
    expect(big.swellPx).toBeGreaterThan(small.swellPx);
    expect(big.swellPx).toBeLessThanOrEqual(14);
  });
});

describe("jellyWobble", () => {
  it("is at rest at t=0 and when jelly is disabled", () => {
    expect(jellyWobble(0, { jelly: 1, bounce: 0.25, stiffness: 580 })).toEqual({
      x: 0,
      y: 0,
    });
    expect(jellyWobble(100, { jelly: 0, bounce: 0.25, stiffness: 580 })).toEqual({
      x: 0,
      y: 0,
    });
  });

  it("decays towards zero and stays bounded", () => {
    const p = { jelly: 1, bounce: 0.25, stiffness: 580 };
    const a1 = jellyWobble(50, p);
    const a2 = jellyWobble(150, p);
    const a3 = jellyWobble(600, p);
    const mag = (v: { x: number; y: number }) => Math.hypot(v.x, v.y);
    expect(mag(a1)).toBeGreaterThan(0);
    expect(mag(a2)).toBeLessThan(mag(a1));
    expect(mag(a3)).toBeLessThan(mag(a2));
    // Never more than ~12° even at full jelly.
    expect(mag(a1)).toBeLessThan(0.12);
  });

  it("rings longer with a higher bounce", () => {
    const soft = jellyWobble(300, { jelly: 1, bounce: 0.1, stiffness: 580 });
    const bouncy = jellyWobble(300, { jelly: 1, bounce: 0.6, stiffness: 580 });
    expect(Math.hypot(bouncy.x, bouncy.y)).toBeGreaterThan(
      Math.hypot(soft.x, soft.y),
    );
  });
});

describe("wobbleSettled", () => {
  it("reports settled once the motion is invisible", () => {
    const p = { jelly: 1, bounce: 0.25 };
    expect(wobbleSettled(0, p)).toBe(false);
    expect(wobbleSettled(5_000, p)).toBe(true);
  });

  it("never starts when jelly is 0", () => {
    expect(wobbleSettled(0, { jelly: 0, bounce: 0.25 })).toBe(true);
  });
});

describe("staggerDelay", () => {
  it("runs the wave outward from the origin chip", () => {
    expect(staggerDelay(2, 2, 22)).toBe(0);
    expect(staggerDelay(1, 2, 22)).toBe(22);
    expect(staggerDelay(4, 2, 22)).toBe(44);
  });

  it("caps the delay at 8 hops so long rows never freeze", () => {
    expect(staggerDelay(20, 0, 22)).toBe(8 * 22);
  });
});
