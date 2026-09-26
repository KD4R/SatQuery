"use client";

/**
 * Pixel-magnet cursor trail.
 *
 * Original implementation (not the React Bits Pro source). The page carries an
 * invisible lattice of pixels. As the pointer moves, it leaves a short trail; every
 * lattice pixel near the trail is pulled toward it and lights up, then springs home
 * and fades once the trail has passed. The native cursor is left alone -- replacing
 * it would cost precision on the one thing people actually click.
 *
 * Cost is bounded by activity, not by screen size: only pixels inside the trail's
 * bounding box are ever touched, and a pixel leaves the active set once it has
 * settled. When nothing is moving the loop stops entirely.
 *
 * Off for touch (there is no hover to trail) and for prefers-reduced-motion.
 */

import { useEffect, useRef } from "react";

import { prefersReducedMotion } from "./canvas";

const SPACING = 20; // lattice pitch, CSS px
const RADIUS = 96; // reach of the magnet
const TRAIL_MS = 420; // how long a trail point stays magnetic
const PIXEL = 2.2; // pixel size at full charge

interface P {
  hx: number; // home
  hy: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  glow: number; // 0..1
}

export function PixelMagnet() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    if (coarse || prefersReducedMotion()) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let dpr = 1;
    let cols = 0;
    let rows = 0;
    const size = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(window.innerWidth * dpr);
      canvas.height = Math.round(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.ceil(window.innerWidth / SPACING) + 1;
      rows = Math.ceil(window.innerHeight / SPACING) + 1;
      active.clear();
    };

    const trail: { x: number; y: number; t: number }[] = [];
    const active = new Map<number, P>();
    let raf = 0;
    let running = false;

    const pixelAt = (c: number, r: number) => {
      const key = r * cols + c;
      let p = active.get(key);
      if (!p) {
        const hx = c * SPACING;
        const hy = r * SPACING;
        p = { hx, hy, x: hx, y: hy, vx: 0, vy: 0, glow: 0 };
        active.set(key, p);
      }
      return p;
    };

    const step = (now: number) => {
      while (trail.length && now - trail[0]!.t > TRAIL_MS) trail.shift();

      // Recruit lattice pixels near the live trail.
      for (const q of trail) {
        const c0 = Math.max(0, Math.floor((q.x - RADIUS) / SPACING));
        const c1 = Math.min(cols - 1, Math.ceil((q.x + RADIUS) / SPACING));
        const r0 = Math.max(0, Math.floor((q.y - RADIUS) / SPACING));
        const r1 = Math.min(rows - 1, Math.ceil((q.y + RADIUS) / SPACING));
        for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) pixelAt(c, r);
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (const [key, p] of active) {
        // Strongest pull from the freshest trail point in reach.
        let fx = 0;
        let fy = 0;
        let charge = 0;
        for (const q of trail) {
          const dx = q.x - p.hx;
          const dy = q.y - p.hy;
          const d = Math.hypot(dx, dy);
          if (d > RADIUS) continue;
          const life = 1 - (now - q.t) / TRAIL_MS;
          const s = (1 - d / RADIUS) ** 2 * life;
          if (s > charge) {
            charge = s;
            fx = dx * 0.42 * s;
            fy = dy * 0.42 * s;
          }
        }

        // Damped spring toward home + magnet offset.
        const tx = p.hx + fx;
        const ty = p.hy + fy;
        p.vx = (p.vx + (tx - p.x) * 0.2) * 0.72;
        p.vy = (p.vy + (ty - p.y) * 0.2) * 0.72;
        p.x += p.vx;
        p.y += p.vy;
        p.glow += (charge - p.glow) * 0.18;

        const settled =
          p.glow < 0.01 && Math.abs(p.x - p.hx) < 0.2 && Math.abs(p.y - p.hy) < 0.2;
        if (settled) {
          active.delete(key);
          continue;
        }

        // Ice at the edge of the field, violet at its heart.
        const g = Math.min(1, p.glow * 1.6);
        const rr = Math.round(125 + (167 - 125) * g);
        const gg = Math.round(211 + (139 - 211) * g);
        const bb = Math.round(252 + (250 - 252) * g);
        const s = PIXEL * (0.6 + g * 0.8);
        ctx.fillStyle = `rgba(${rr},${gg},${bb},${Math.min(0.95, g * 1.1)})`;
        ctx.fillRect(p.x - s / 2, p.y - s / 2, s, s);
      }

      if (active.size || trail.length) {
        raf = requestAnimationFrame(step);
      } else {
        running = false;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    };

    const onMove = (ev: PointerEvent) => {
      if (ev.pointerType === "touch") return;
      trail.push({ x: ev.clientX, y: ev.clientY, t: performance.now() });
      if (trail.length > 24) trail.shift();
      if (!running) {
        running = true;
        raf = requestAnimationFrame(step);
      }
    };

    size();
    window.addEventListener("resize", size);
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", size);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return <canvas ref={ref} aria-hidden="true" className="sq-magnet" />;
}
