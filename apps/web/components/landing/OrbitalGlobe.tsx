"use client";

/**
 * The orbital globe (landing page).
 *
 * Canvas 2D, drawn from maths — no textures, no model files, no third-party
 * assets, nothing fetched. That matters for three reasons: the browser may only
 * call the gateway, the projector demo has to work with no network, and a
 * procedural globe stays crisp at 2560px where a bitmap would not.
 *
 * What is drawn, back to front: the graticule sphere with correct hidden-line
 * removal (meridians and parallels behind the limb are dimmed, not clipped, which
 * is what makes it read as a wireframe rather than a flat circle), then the
 * orbital traces, then the satellites riding them, then the ground-station ticks.
 *
 * Rotation is driven by elapsed time and the whole thing is a pure function of
 * `t`, so a reduced-motion viewer gets the identical scene frozen at t=0 rather
 * than a different, static drawing.
 */

import { useEffect, useRef } from "react";

interface Orbit {
  /** Semi-major axis as a multiple of the globe radius. */
  a: number;
  /** Inclination and ascending-node longitude, radians. */
  inc: number;
  raan: number;
  /** Orbits per second of wall time. */
  rate: number;
  phase: number;
  eccentricity: number;
}

/** Fixed constellation. No randomness: the scene is identical on every load. */
const ORBITS: Orbit[] = [
  { a: 1.14, inc: 0.62, raan: 0.2, rate: 0.055, phase: 0.0, eccentricity: 0.05 },
  { a: 1.3, inc: -0.48, raan: 1.9, rate: 0.041, phase: 1.3, eccentricity: 0.1 },
  { a: 1.08, inc: 1.42, raan: 0.9, rate: 0.068, phase: 2.6, eccentricity: 0.02 },
  { a: 1.52, inc: 0.28, raan: 3.4, rate: 0.029, phase: 0.7, eccentricity: 0.16 },
  { a: 1.22, inc: -1.15, raan: 2.7, rate: 0.048, phase: 4.1, eccentricity: 0.04 },
];

type V3 = [number, number, number];

function rotY([x, y, z]: V3, a: number): V3 {
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [c * x + s * z, y, -s * x + c * z];
}

function rotX([x, y, z]: V3, a: number): V3 {
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [x, c * y - s * z, s * y + c * z];
}

/** Slight tilt so the pole is visible — a dead-on equator view reads as a circle. */
const TILT = -0.38;

export function OrbitalGlobe({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let stopped = false;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const { clientWidth: w, clientHeight: h } = canvas;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.min(w, h) * 0.3;
      const spin = t * 0.08;

      ctx.clearRect(0, 0, w, h);

      /* ── graticule ────────────────────────────────────────────────────── */

      const project = (lat: number, lon: number): { x: number; y: number; z: number } => {
        const p: V3 = [
          Math.cos(lat) * Math.cos(lon),
          Math.sin(lat),
          Math.cos(lat) * Math.sin(lon),
        ];
        const [x, y, z] = rotX(rotY(p, spin), TILT);
        return { x: cx + x * R, y: cy - y * R, z };
      };

      const strokeArc = (
        points: { x: number; y: number; z: number }[],
        front: string,
        back: string,
      ) => {
        // Split at the limb so the far side can be drawn dimmer. Dimming rather
        // than hiding is what gives the wireframe its depth.
        let run: { x: number; y: number }[] = [];
        let runFront = points[0] ? points[0].z >= 0 : true;
        const flush = () => {
          if (run.length < 2) {
            run = [];
            return;
          }
          ctx.beginPath();
          ctx.moveTo(run[0]!.x, run[0]!.y);
          for (const q of run.slice(1)) ctx.lineTo(q.x, q.y);
          ctx.strokeStyle = runFront ? front : back;
          ctx.stroke();
          run = [];
        };
        for (const p of points) {
          const isFront = p.z >= 0;
          if (isFront !== runFront) {
            flush();
            runFront = isFront;
          }
          run.push(p);
        }
        flush();
      };

      ctx.lineWidth = 1;

      // Parallels every 20°.
      for (let latDeg = -80; latDeg <= 80; latDeg += 20) {
        const lat = (latDeg * Math.PI) / 180;
        const pts = [];
        for (let i = 0; i <= 96; i++) {
          pts.push(project(lat, (i / 96) * Math.PI * 2));
        }
        const equator = latDeg === 0;
        strokeArc(
          pts,
          equator ? "rgba(255,255,255,0.30)" : "rgba(255,255,255,0.13)",
          equator ? "rgba(255,255,255,0.09)" : "rgba(255,255,255,0.045)",
        );
      }

      // Meridians every 30°.
      for (let lonDeg = 0; lonDeg < 360; lonDeg += 30) {
        const lon = (lonDeg * Math.PI) / 180;
        const pts = [];
        for (let i = 0; i <= 96; i++) {
          pts.push(project(-Math.PI / 2 + (i / 96) * Math.PI, lon));
        }
        strokeArc(pts, "rgba(255,255,255,0.13)", "rgba(255,255,255,0.045)");
      }

      // The limb, drawn last so it sits cleanly over the graticule ends.
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.34)";
      ctx.stroke();

      /* ── orbits ───────────────────────────────────────────────────────── */

      for (const o of ORBITS) {
        const pts: { x: number; y: number; z: number }[] = [];
        for (let i = 0; i <= 160; i++) {
          const nu = (i / 160) * Math.PI * 2;
          // Ellipse in the orbital plane, focus at the centre.
          const r =
            (o.a * (1 - o.eccentricity * o.eccentricity)) /
            (1 + o.eccentricity * Math.cos(nu));
          let p: V3 = [r * Math.cos(nu), 0, r * Math.sin(nu)];
          p = rotX(p, o.inc);
          p = rotY(p, o.raan + spin * 0.35);
          const [x, y, z] = rotX(p, TILT);
          pts.push({ x: cx + x * R, y: cy - y * R, z });
        }
        strokeArc(pts, "rgba(255,59,48,0.55)", "rgba(255,59,48,0.16)");

        // The satellite on this orbit.
        const nu = o.phase + t * o.rate * Math.PI * 2;
        const r =
          (o.a * (1 - o.eccentricity * o.eccentricity)) /
          (1 + o.eccentricity * Math.cos(nu));
        let sp: V3 = [r * Math.cos(nu), 0, r * Math.sin(nu)];
        sp = rotX(sp, o.inc);
        sp = rotY(sp, o.raan + spin * 0.35);
        const [sx, sy, sz] = rotX(sp, TILT);
        const px = cx + sx * R;
        const py = cy - sy * R;

        ctx.beginPath();
        ctx.arc(px, py, sz >= 0 ? 2.1 : 1.4, 0, Math.PI * 2);
        ctx.fillStyle = sz >= 0 ? "#ff3b30" : "rgba(255,59,48,0.35)";
        ctx.fill();

        // Nadir tick: where this satellite is looking.
        if (sz >= 0) {
          const len = Math.hypot(sx, sy, sz) || 1;
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(cx + (sx / len) * R, cy - (sy / len) * R);
          ctx.strokeStyle = "rgba(255,59,48,0.18)";
          ctx.stroke();
        }
      }

      if (!stopped && !reduce) raf = requestAnimationFrame(() => draw(performance.now() / 1000));
    };

    resize();
    draw(reduce ? 0 : performance.now() / 1000);

    const onResize = () => {
      resize();
      draw(reduce ? 0 : performance.now() / 1000);
    };
    window.addEventListener("resize", onResize);

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      className={className}
      role="img"
      aria-label="Orbital diagram: a wireframe globe with five satellite tracks."
      style={{ width: "100%", height: "100%", display: "block" }}
    />
  );
}
