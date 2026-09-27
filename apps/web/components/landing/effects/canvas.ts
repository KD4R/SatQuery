"use client";

/**
 * Shared plumbing for the landing page's canvas effects.
 *
 * Every effect on the page is a canvas redrawn per frame, and five of them running
 * flat-out would cook a laptop on a projector cart. So each one goes through the same
 * loop, which enforces the same four rules:
 *
 *   1. Paused while offscreen. An IntersectionObserver gates the rAF loop, so the
 *      landscape costs nothing while you are reading the hero.
 *   2. Paused while the tab is hidden.
 *   3. Device pixel ratio capped at 2. A 3x phone screen gets a 2x canvas; nobody
 *      can see the difference and it is 2.25x fewer pixels to fill.
 *   4. prefers-reduced-motion draws one frame and stops. The scene is a pure
 *      function of time, so a reduced-motion viewer sees the same picture, still.
 *
 * Randomness is seeded (mulberry32), so stars, terrain and glitch timing are
 * identical on every load. The landing page is shown to judges on a projector;
 * it should look the same the second time as it did in rehearsal.
 */

import { useEffect, useRef } from "react";

/** Deterministic PRNG. Same seed, same sequence, every browser. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export interface Frame {
  ctx: CanvasRenderingContext2D;
  /** CSS pixels. */
  w: number;
  h: number;
  /** Seconds since the loop started. */
  t: number;
  /** Seconds since the previous frame, clamped so a backgrounded tab cannot jump. */
  dt: number;
  reduced: boolean;
}

export interface LoopOptions {
  /**
   * Return false from draw() to say "nothing changed, skip until something wakes
   * me". wake() restarts the loop -- used by effects that are idle until the cursor
   * moves.
   */
  alwaysRun?: boolean;
  /** Extra values that should force a resize + redraw when they change. */
  deps?: readonly unknown[];
}

/**
 * Drive a canvas with the four rules above. `draw` may change between renders; the
 * latest one is always used, without restarting the loop.
 */
export function useCanvasLoop(
  draw: (f: Frame) => boolean | void,
  { alwaysRun = true, deps = [] }: LoopOptions = {},
) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawRef = useRef(draw);
  drawRef.current = draw;
  const wakeRef = useRef<() => void>(() => undefined);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = prefersReducedMotion();
    let raf = 0;
    let running = false;
    let onScreen = true;
    let hidden = document.visibilityState === "hidden";
    const start = performance.now();
    let last = start;

    const size = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { w, h };
    };

    let dims = size();

    const frame = (now: number) => {
      // rAF timestamps can precede the performance.now() taken at scheduling.
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;
      const keepGoing = drawRef.current({
        ctx,
        w: dims.w,
        h: dims.h,
        t: reduced ? 0 : Math.max(0, (now - start) / 1000),
        dt: reduced ? 0 : dt,
        reduced,
      });
      if (reduced || !onScreen || hidden || (!alwaysRun && keepGoing === false)) {
        running = false;
        return;
      }
      raf = requestAnimationFrame(frame);
    };

    const wake = () => {
      if (running || reduced || !onScreen || hidden) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    };
    wakeRef.current = wake;

    // First paint happens even when reduced-motion is on: that frame IS the scene.
    running = true;
    raf = requestAnimationFrame(frame);

    const io = new IntersectionObserver(
      ([entry]) => {
        onScreen = Boolean(entry?.isIntersecting);
        if (onScreen) wake();
      },
      { rootMargin: "120px" },
    );
    io.observe(canvas);

    const ro = new ResizeObserver(() => {
      dims = size();
      // A resize must repaint even when paused, or the canvas blanks (setting
      // canvas.width clears it).
      const t = reduced ? 0 : (performance.now() - start) / 1000;
      drawRef.current({ ctx, w: dims.w, h: dims.h, t, dt: 0, reduced });
      wake();
    });
    ro.observe(canvas);

    const onVis = () => {
      hidden = document.visibilityState === "hidden";
      if (!hidden) wake();
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
      ro.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      running = false;
    };
    // deps are caller-supplied; the loop reads draw through a ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [alwaysRun, ...deps]);

  return { canvasRef, wake: () => wakeRef.current() };
}
