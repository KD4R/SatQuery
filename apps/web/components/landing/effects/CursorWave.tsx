"use client";

/**
 * Cursor wave: a field of small marks behind the closing section that swell around the cursor
 * and ripple outward from a click.
 *
 * Written for this page, after the behaviour of the React Bits Pro "Cursor Wave"
 * component (which needs a paid licence): a grid of circles, triangles and squares,
 * an influence radius in vmin, separate attack and release times, and a burst ring
 * with a speed and a thickness. Colours come from the page tokens -- mostly slate,
 * with the three data colours showing only where the field is excited -- so at rest
 * it reads as a quiet measurement grid, not decoration.
 *
 * Cost: it draws only while something is changing. At rest the canvas holds one
 * static frame and no animation frame is scheduled; offscreen it stops entirely.
 * Reduced motion gets the static frame and no interaction.
 */

import { useEffect, useRef } from "react";

import { mulberry32, prefersReducedMotion } from "./canvas";

type Shape = 0 | 1 | 2; // circle, triangle, square

interface Props {
  className?: string;
  /** Grid pitch in CSS pixels. */
  cellSize?: number;
  /** Radius of the cursor's influence, as a percentage of the viewport's short side. */
  influenceRadiusVmin?: number;
  /** Seconds to rise toward full activation, and to fall back. */
  attackTime?: number;
  releaseTime?: number;
  /** Mark size as a fraction of the cell, at rest and at full activation. */
  idleScale?: number;
  peakScale?: number;
  /** Burst ring speed (px/s) and thickness (px). */
  burstSpeed?: number;
  burstThickness?: number;
  /** Rest colour, and the colours marks take when excited. */
  restColor?: string;
  colors?: string[];
  opacity?: number;
}

const DEFAULT_COLORS = [
  // weighted toward slate: most of the field stays neutral even when excited
  "#98a0a8",
  "#98a0a8",
  "#b9bec4",
  "#b9bec4",
  "#626970",
  "#30d098", // --c-data-a
  "#60a0f8", // --c-data-b
  "#f87010", // --c-signal
];

interface Burst {
  x: number;
  y: number;
  t0: number;
}

export function CursorWave({
  className,
  cellSize = 36,
  influenceRadiusVmin = 22,
  attackTime = 0.35,
  releaseTime = 0.9,
  idleScale = 0.08,
  peakScale = 0.46,
  burstSpeed = 900,
  burstThickness = 110,
  restColor = "#626970",
  colors = DEFAULT_COLORS,
  opacity = 1,
}: Props) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    const host = canvas?.parentElement;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !host || !ctx) return;

    const reduced = prefersReducedMotion();
    let w = 0;
    let h = 0;
    let cols = 0;
    let rows = 0;
    let shape = new Uint8Array(0);
    let tint = new Uint8Array(0);
    let level = new Float32Array(0);

    let px = -1e5;
    let py = -1e5;
    let inside = false;
    const bursts: Burst[] = [];

    let raf = 0;
    let last = 0;
    let onScreen = true;

    const layout = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = host.clientWidth;
      h = host.clientHeight;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.ceil(w / cellSize) + 1;
      rows = Math.ceil(h / cellSize) + 1;
      const n = cols * rows;
      const rand = mulberry32(7);
      shape = new Uint8Array(n);
      tint = new Uint8Array(n);
      for (let i = 0; i < n; i++) {
        shape[i] = Math.floor(rand() * 3);
        tint[i] = Math.floor(rand() * colors.length);
      }
      level = new Float32Array(n);
    };

    const mark = (
      target: CanvasRenderingContext2D | Path2D,
      s: Shape,
      x: number,
      y: number,
      r: number,
    ) => {
      if (s === 0) {
        target.moveTo(x + r, y);
        target.arc(x, y, r, 0, Math.PI * 2);
      } else if (s === 1) {
        target.moveTo(x, y - r);
        target.lineTo(x + r * 0.95, y + r * 0.7);
        target.lineTo(x - r * 0.95, y + r * 0.7);
        target.closePath();
      } else {
        target.rect(x - r * 0.8, y - r * 0.8, r * 1.6, r * 1.6);
      }
    };

    // Offset every other row by half a cell: a staggered grid reads as a field,
    // a square one as graph paper.
    const cx = (c: number, r: number) =>
      c * cellSize + (r % 2 ? cellSize / 2 : 0);
    const cy = (r: number) => r * cellSize + cellSize / 2;

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.globalAlpha = opacity;
      const rest = new Path2D();
      const restR = (cellSize * idleScale) / 2;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const i = r * cols + c;
          const v = level[i]!;
          if (v < 0.01) {
            mark(rest, shape[i] as Shape, cx(c, r), cy(r), restR);
            continue;
          }
          const size =
            (cellSize * (idleScale + (peakScale - idleScale) * v)) / 2;
          ctx.globalAlpha = opacity * (0.3 + 0.5 * v);
          ctx.fillStyle = v > 0.18 ? colors[tint[i]!]! : restColor;
          ctx.beginPath();
          mark(ctx, shape[i] as Shape, cx(c, r), cy(r), size);
          ctx.fill();
        }
      }
      ctx.globalAlpha = opacity * 0.5;
      ctx.fillStyle = restColor;
      ctx.fill(rest);
      ctx.globalAlpha = 1;
    };

    const step = (now: number) => {
      raf = 0;
      const t = now / 1000;
      const dt = Math.min(0.05, Math.max(0, t - last));
      last = t;
      const R =
        (influenceRadiusVmin / 100) *
        Math.min(window.innerWidth, window.innerHeight);
      const up = 1 - Math.exp(-dt / attackTime);
      const down = 1 - Math.exp(-dt / releaseTime);
      const maxRing = Math.hypot(w, h);

      for (let k = bursts.length - 1; k >= 0; k--) {
        if ((t - bursts[k]!.t0) * burstSpeed > maxRing + burstThickness * 2)
          bursts.splice(k, 1);
      }

      let busy = bursts.length > 0;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const i = r * cols + c;
          const x = cx(c, r);
          const y = cy(r);
          let target = 0;
          if (inside) {
            const d = Math.hypot(x - px, y - py);
            if (d < R) target = (1 - d / R) ** 2;
          }
          for (const b of bursts) {
            const ring = (t - b.t0) * burstSpeed;
            const d = Math.hypot(x - b.x, y - b.y);
            const k =
              Math.exp(-(((d - ring) / burstThickness) ** 2)) *
              Math.max(0, 1 - ring / maxRing);
            if (k > target) target = k;
          }
          const v = level[i]!;
          const next = v + (target - v) * (target > v ? up : down);
          level[i] = next < 0.002 ? 0 : next;
          if (Math.abs(target - level[i]!) > 0.004 || level[i]! > 0)
            busy = true;
        }
      }
      draw();
      if (busy && onScreen) raf = requestAnimationFrame(step);
    };

    const wake = () => {
      if (raf || reduced || !onScreen) return;
      last = performance.now() / 1000;
      raf = requestAnimationFrame(step);
    };

    const onMove = (e: PointerEvent) => {
      if (e.pointerType === "touch") return;
      const rect = canvas.getBoundingClientRect();
      px = e.clientX - rect.left;
      py = e.clientY - rect.top;
      inside = px >= 0 && py >= 0 && px <= rect.width && py <= rect.height;
      wake();
    };
    const onLeave = () => {
      inside = false;
      wake();
    };
    const onDown = (e: PointerEvent) => {
      // A click on something that does its own thing (a link, a button, the globe
      // being dragged) is not a request for a ripple.
      if (
        (e.target as Element | null)?.closest(
          "a, button, input, textarea, .sq-globe-canvas",
        )
      )
        return;
      const rect = canvas.getBoundingClientRect();
      bursts.push({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        t0: performance.now() / 1000,
      });
      if (bursts.length > 4) bursts.shift();
      wake();
    };

    layout();
    draw();

    const ro = new ResizeObserver(() => {
      layout();
      draw();
    });
    ro.observe(host);

    if (reduced) return () => ro.disconnect();

    const io = new IntersectionObserver(([entry]) => {
      onScreen = !!entry?.isIntersecting;
      if (onScreen) wake();
    });
    io.observe(canvas);

    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    host.addEventListener("pointerdown", onDown);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      host.removeEventListener("pointerdown", onDown);
    };
  }, [
    cellSize,
    influenceRadiusVmin,
    attackTime,
    releaseTime,
    idleScale,
    peakScale,
    burstSpeed,
    burstThickness,
    restColor,
    colors,
    opacity,
  ]);

  return <canvas ref={ref} aria-hidden="true" className={className} />;
}
