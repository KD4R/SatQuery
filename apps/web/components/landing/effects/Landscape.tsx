"use client";

/**
 * Procedural landscape scrolling toward the horizon.
 *
 * Original implementation (not the React Bits Pro source). A seeded value-noise
 * heightfield is flown over at constant speed and drawn as glowing contour rows,
 * far to near, each row filling the ground beneath it so nearer terrain occludes
 * farther terrain. A ringed planet sits on the horizon.
 *
 * It is also the argument of the section it sits in. A radar pulse sweeps across the
 * ground every few seconds and lights the terrain it hits -- except the water in the
 * valleys, which stays black. That is what Sentinel-1 actually sees: rough ground
 * scatters the pulse back to the satellite, calm water mirrors it away. Dark means
 * water. The model learns exactly that contrast.
 */

import { useMemo } from "react";

import { mulberry32, useCanvasLoop } from "./canvas";

const COLS = 72;
const ROWS = 54;
const WATER = 0.3; // water level, world units
const SPEED = 1.35; // world units per second
const SWEEP_S = 4.2; // seconds per radar sweep

/** Seeded 2D value noise with smoothstep interpolation. */
function makeNoise(seed: number) {
  const rand = mulberry32(seed);
  const N = 256;
  const table = new Float32Array(N * N);
  for (let i = 0; i < table.length; i++) table[i] = rand();
  const at = (x: number, y: number) => table[(((y % N) + N) % N) * N + (((x % N) + N) % N)]!;
  const smooth = (t: number) => t * t * (3 - 2 * t);
  const noise = (x: number, y: number) => {
    const xi = Math.floor(x);
    const yi = Math.floor(y);
    const xf = smooth(x - xi);
    const yf = smooth(y - yi);
    const a = at(xi, yi);
    const b = at(xi + 1, yi);
    const c = at(xi, yi + 1);
    const d = at(xi + 1, yi + 1);
    return a + (b - a) * xf + (c - a) * yf + (a - b - c + d) * xf * yf;
  };
  return (x: number, y: number) =>
    noise(x, y) * 0.55 + noise(x * 2.1, y * 2.1) * 0.3 + noise(x * 4.3, y * 4.3) * 0.15;
}

export function Landscape({ className }: { className?: string }) {
  const fbm = useMemo(() => makeNoise(1947), []);
  const stars = useMemo(() => {
    const r = mulberry32(88);
    return Array.from({ length: 140 }, () => ({ x: r(), y: r() * 0.5, s: 0.4 + r() * 1.1, a: 0.3 + r() * 0.7 }));
  }, []);

  const { canvasRef } = useCanvasLoop(({ ctx, w, h, t }) => {
    const horizon = h * 0.5;
    const cx = w / 2;
    const f = h * 0.95;
    const camY = 1.55;
    const travel = t * SPEED;

    /* ── sky ──────────────────────────────────────────────────────────── */
    const sky = ctx.createLinearGradient(0, 0, 0, horizon);
    sky.addColorStop(0, "#080808");
    sky.addColorStop(0.6, "#0c0d0e");
    sky.addColorStop(1, "#16181a");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, w, horizon + 2);

    for (const s of stars) {
      ctx.fillStyle = `rgba(236,237,238,${s.a * 0.7})`;
      ctx.fillRect(s.x * w, s.y * horizon, s.s, s.s);
    }

    /* ── ringed planet on the horizon ─────────────────────────────────── */
    const pr = Math.min(w, h) * 0.2;
    const px = w * 0.7;
    const py = horizon + pr * 0.18;
    const glow = ctx.createRadialGradient(px, py, pr * 0.8, px, py, pr * 2.1);
    glow.addColorStop(0, "rgba(152,160,168,0.08)");
    glow.addColorStop(1, "rgba(152,160,168,0)");
    ctx.fillStyle = glow;
    ctx.fillRect(px - pr * 2.2, py - pr * 2.2, pr * 4.4, pr * 4.4);

    // back half of the ring, behind the planet
    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(-0.22);
    ctx.strokeStyle = "rgba(152,160,168,0.28)";
    ctx.lineWidth = pr * 0.05;
    ctx.beginPath();
    ctx.ellipse(0, 0, pr * 1.75, pr * 0.34, 0, Math.PI, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    const body = ctx.createRadialGradient(px - pr * 0.4, py - pr * 0.5, pr * 0.1, px, py, pr);
    body.addColorStop(0, "#9aa1a8");
    body.addColorStop(0.45, "#3a3f44");
    body.addColorStop(1, "#101214");
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.arc(px, py, pr, 0, Math.PI * 2);
    ctx.fill();

    ctx.save();
    ctx.translate(px, py);
    ctx.rotate(-0.22);
    ctx.strokeStyle = "rgba(185,190,196,0.45)";
    ctx.lineWidth = pr * 0.05;
    ctx.beginPath();
    ctx.ellipse(0, 0, pr * 1.75, pr * 0.34, 0, 0, Math.PI);
    ctx.stroke();
    ctx.restore();

    // horizon haze
    const haze = ctx.createLinearGradient(0, horizon - h * 0.08, 0, horizon + h * 0.04);
    haze.addColorStop(0, "rgba(152,160,168,0)");
    haze.addColorStop(0.7, "rgba(152,160,168,0.06)");
    haze.addColorStop(1, "rgba(152,160,168,0)");
    ctx.fillStyle = haze;
    ctx.fillRect(0, horizon - h * 0.08, w, h * 0.12);

    // Ground beyond the farthest row. Without it the sky gradient shows through the
    // valley at the horizon and reads as glowing water -- the opposite of the point.
    ctx.fillStyle = "#080808";
    ctx.fillRect(0, horizon, w, h - horizon);
    const rim = ctx.createLinearGradient(0, horizon - 2, 0, horizon + h * 0.03);
    rim.addColorStop(0, "rgba(152,160,168,0.12)");
    rim.addColorStop(1, "rgba(152,160,168,0)");
    ctx.fillStyle = rim;
    ctx.fillRect(0, horizon - 2, w, h * 0.03 + 2);

    /* ── terrain, far to near ─────────────────────────────────────────── */
    const zNear = 0.9;
    const dz = 0.42;
    const halfW = 11;
    const sweep = (t % SWEEP_S) / SWEEP_S; // 0 = near, 1 = far
    const frac = travel % dz;

    const xs = new Float32Array(COLS + 1);
    const ys = new Float32Array(COLS + 1);
    const wet = new Uint8Array(COLS + 1);

    for (let k = ROWS - 1; k >= 0; k--) {
      const z = zNear + k * dz - frac;
      if (z <= 0.2) continue;
      const worldZ = z + travel;
      const depth = k / (ROWS - 1); // 0 near .. 1 far

      for (let i = 0; i <= COLS; i++) {
        const x = -halfW + (i / COLS) * halfW * 2;
        // A valley runs down the middle: low near x=0, rising to either side.
        const valley = Math.min(1, (Math.abs(x) / 4.2) ** 1.6);
        let y = fbm(x * 0.32 + 40, worldZ * 0.32) * (0.35 + valley * 2.3) - 0.05;
        const isWet = y < WATER;
        if (isWet) y = WATER;
        wet[i] = isWet ? 1 : 0;
        xs[i] = cx + (x * f) / z;
        ys[i] = horizon + ((camY - y) * f) / z;
      }

      // ground fill beneath this row occludes everything farther away
      ctx.beginPath();
      ctx.moveTo(xs[0]!, h);
      for (let i = 0; i <= COLS; i++) ctx.lineTo(xs[i]!, ys[i]!);
      ctx.lineTo(xs[COLS]!, h);
      ctx.closePath();
      ctx.fillStyle = "#080808";
      ctx.fill();

      const fade = (1 - depth) ** 1.1;
      const pulse = Math.exp(-(((depth - sweep) / 0.045) ** 2));

      // land: slate by default, signal orange where the radar pulse is passing
      ctx.beginPath();
      let pen = false;
      for (let i = 0; i <= COLS; i++) {
        const landSeg = !wet[i] || (i > 0 && !wet[i - 1]);
        if (landSeg) {
          if (!pen) ctx.moveTo(xs[i]!, ys[i]!);
          else ctx.lineTo(xs[i]!, ys[i]!);
          pen = true;
        } else pen = false;
      }
      const a = 0.08 + fade * 0.42 + pulse * 0.55;
      ctx.strokeStyle = pulse > 0.3 ? `rgba(248,112,16,${Math.min(1, a)})` : `rgba(152,160,168,${a * 0.85})`;
      ctx.lineWidth = 0.7 + fade * 0.8 + pulse * 0.8;
      ctx.stroke();

      // water: flat and dark, and the pulse does not light it
      ctx.beginPath();
      pen = false;
      for (let i = 0; i <= COLS; i++) {
        if (wet[i] && (i === 0 || wet[i - 1])) {
          if (!pen) ctx.moveTo(xs[i - 1 >= 0 ? i - 1 : 0]!, ys[i - 1 >= 0 ? i - 1 : 0]!);
          ctx.lineTo(xs[i]!, ys[i]!);
          pen = true;
        } else pen = false;
      }
      ctx.strokeStyle = `rgba(96,160,248,${0.04 + fade * 0.1})`;
      ctx.lineWidth = 0.6;
      ctx.stroke();
    }

    // vignette so the section's copy sits on something calm
    const vig = ctx.createLinearGradient(0, 0, 0, h);
    vig.addColorStop(0, "rgba(8,8,8,0.6)");
    vig.addColorStop(0.35, "rgba(8,8,8,0)");
    vig.addColorStop(0.8, "rgba(8,8,8,0)");
    vig.addColorStop(1, "rgba(8,8,8,0.92)");
    ctx.fillStyle = vig;
    ctx.fillRect(0, 0, w, h);
  });

  return <canvas ref={canvasRef} aria-hidden="true" className={className} />;
}
