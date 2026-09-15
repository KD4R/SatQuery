"use client";

/**
 * The Earth (landing page).
 *
 * Real geography: Natural Earth 1:50m land polygons, orthographically projected and
 * drawn to a 2D canvas each frame. No bitmap texture — a texture that looks right at
 * 1600px is mush on a 2560px projector, and an orthographic projection of real
 * vectors stays sharp at any size. The land data ships as a static asset and is
 * fetched same-origin, so nothing here reaches outside the app.
 *
 * What makes it read as a planet rather than a circle with shapes on it:
 *
 *   - A lit hemisphere. Ocean and land are both shaded by a radial gradient offset
 *     toward a fixed sun direction, so brightness falls off toward the terminator.
 *   - An atmospheric limb. A narrow blue glow just outside the disc, plus a faint
 *     inner rim — the single cheapest cue that a sphere has air on it.
 *   - Night side. The far edge falls to near-black rather than to flat mid-grey.
 *
 * Everything is a pure function of elapsed time, so a reduced-motion viewer sees the
 * identical scene frozen at t=0, not a different drawing.
 */

import {
  geoDistance,
  geoGraticule10,
  geoOrthographic,
  geoPath,
  type GeoProjection,
} from "d3-geo";
import { useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";
import type { FeatureCollection } from "geojson";

interface Orbit {
  a: number;
  inc: number;
  raan: number;
  rate: number;
  phase: number;
  eccentricity: number;
}

/** Fixed constellation — no randomness, so the scene is identical on every load. */
const ORBITS: Orbit[] = [
  { a: 1.16, inc: 0.62, raan: 0.2, rate: 0.055, phase: 0.0, eccentricity: 0.05 },
  { a: 1.34, inc: -0.48, raan: 1.9, rate: 0.041, phase: 1.3, eccentricity: 0.1 },
  { a: 1.09, inc: 1.42, raan: 0.9, rate: 0.068, phase: 2.6, eccentricity: 0.02 },
  { a: 1.55, inc: 0.28, raan: 3.4, rate: 0.029, phase: 0.7, eccentricity: 0.16 },
  { a: 1.24, inc: -1.15, raan: 2.7, rate: 0.048, phase: 4.1, eccentricity: 0.04 },
];

/** Sun direction in screen space: upper-left, so the terminator falls lower-right. */
const SUN: [number, number] = [-0.42, -0.38];

type V3 = [number, number, number];

const rotY = ([x, y, z]: V3, a: number): V3 => [
  Math.cos(a) * x + Math.sin(a) * z,
  y,
  -Math.sin(a) * x + Math.cos(a) * z,
];

const rotX = ([x, y, z]: V3, a: number): V3 => [
  x,
  Math.cos(a) * y - Math.sin(a) * z,
  Math.sin(a) * y + Math.cos(a) * z,
];

const TILT = -0.36;

/** AOI marker: the Assam floodplain the console analyses. */
const ASSAM: [number, number] = [93.896, 26.791];

export function OrbitalGlobe({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const [land, setLand] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    let live = true;
    fetch("/geo/land-50m.json")
      .then((r) => r.json())
      .then((topo: Topology) => {
        if (!live) return;
        const fc = feature(topo, topo.objects.land!) as unknown as FeatureCollection;
        setLand(fc);
      })
      // The globe still draws — ocean, graticule, orbits — without coastlines.
      // A landing page that fails to render because one asset 404'd is worse than
      // one that renders a featureless planet.
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

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
      canvas.width = Math.max(1, Math.floor(canvas.clientWidth * dpr));
      canvas.height = Math.max(1, Math.floor(canvas.clientHeight * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const cx = w / 2;
      const cy = h / 2;
      const R = Math.min(w, h) * 0.31;
      const spinDeg = (t * 4.2) % 360;

      ctx.clearRect(0, 0, w, h);

      const projection: GeoProjection = geoOrthographic()
        .scale(R)
        .translate([cx, cy])
        .rotate([spinDeg, -14, 0])
        .clipAngle(90);
      const path = geoPath(projection, ctx);

      const sx = cx + SUN[0] * R;
      const sy = cy + SUN[1] * R;

      /* ── atmosphere, outside the disc ─────────────────────────────────── */

      const halo = ctx.createRadialGradient(cx, cy, R * 0.97, cx, cy, R * 1.13);
      halo.addColorStop(0, "rgba(74,158,255,0.20)");
      halo.addColorStop(0.45, "rgba(74,158,255,0.07)");
      halo.addColorStop(1, "rgba(74,158,255,0)");
      ctx.beginPath();
      ctx.arc(cx, cy, R * 1.13, 0, Math.PI * 2);
      ctx.fillStyle = halo;
      ctx.fill();

      /* ── ocean, lit from the sun direction ────────────────────────────── */

      const ocean = ctx.createRadialGradient(sx, sy, R * 0.05, cx, cy, R * 1.45);
      ocean.addColorStop(0, "#1d4f80");
      ocean.addColorStop(0.32, "#123553");
      ocean.addColorStop(0.62, "#0a1e33");
      ocean.addColorStop(1, "#02060c");
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = ocean;
      ctx.fill();

      /* ── land ─────────────────────────────────────────────────────────── */

      if (land) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(cx, cy, R, 0, Math.PI * 2);
        ctx.clip();

        ctx.beginPath();
        path(land);
        const terrain = ctx.createRadialGradient(sx, sy, R * 0.05, cx, cy, R * 1.45);
        terrain.addColorStop(0, "#4a5a42");
        terrain.addColorStop(0.32, "#39472f");
        terrain.addColorStop(0.62, "#1f2a1c");
        terrain.addColorStop(1, "#070c07");
        ctx.fillStyle = terrain;
        ctx.fill();

        ctx.lineWidth = 0.6;
        ctx.strokeStyle = "rgba(150,200,255,0.16)";
        ctx.stroke();
        ctx.restore();
      }

      /* ── graticule, very faint ────────────────────────────────────────── */

      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.clip();
      ctx.beginPath();
      path(geoGraticule10());
      ctx.lineWidth = 0.5;
      ctx.strokeStyle = "rgba(255,255,255,0.055)";
      ctx.stroke();
      ctx.restore();

      /* ── terminator: darken away from the sun ─────────────────────────── */

      const night = ctx.createRadialGradient(sx, sy, R * 0.25, cx, cy, R * 1.5);
      night.addColorStop(0, "rgba(0,0,0,0)");
      night.addColorStop(0.55, "rgba(0,0,0,0.12)");
      night.addColorStop(0.85, "rgba(0,0,0,0.55)");
      night.addColorStop(1, "rgba(0,0,0,0.88)");
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = night;
      ctx.fill();

      /* ── inner rim: the atmosphere seen edge-on ───────────────────────── */

      const rim = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R);
      rim.addColorStop(0, "rgba(120,190,255,0)");
      rim.addColorStop(1, "rgba(120,190,255,0.30)");
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.fillStyle = rim;
      ctx.fill();

      /* ── AOI marker, only while on the near side ──────────────────────── */

      // projection() happily returns screen coordinates for points on the FAR side
      // of the globe -- only geoPath clips. Without this check the marker draws
      // straight through the planet. rotate() is [lambda, phi], so the point
      // currently facing the camera is [-lambda, -phi].
      const rot = projection.rotate();
      const centre: [number, number] = [-rot[0], -rot[1]];
      const visible = geoDistance(ASSAM, centre) < Math.PI / 2;

      const aoi = visible ? projection(ASSAM) : null;
      if (aoi) {
        const pulse = 0.55 + 0.45 * Math.sin(t * 2.2);
        ctx.beginPath();
        ctx.arc(aoi[0], aoi[1], 2.4, 0, Math.PI * 2);
        ctx.fillStyle = "#ff3b30";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(aoi[0], aoi[1], 5 + pulse * 4, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255,59,48,${0.5 - pulse * 0.3})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      /* ── orbits ───────────────────────────────────────────────────────── */

      const spin = (spinDeg * Math.PI) / 180;

      const strokeSplit = (
        pts: { x: number; y: number; z: number }[],
        front: string,
        back: string,
      ) => {
        let run: { x: number; y: number }[] = [];
        let isFront = pts[0] ? pts[0].z >= 0 : true;
        const flush = () => {
          if (run.length > 1) {
            ctx.beginPath();
            ctx.moveTo(run[0]!.x, run[0]!.y);
            for (const q of run.slice(1)) ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = isFront ? front : back;
            ctx.stroke();
          }
          run = [];
        };
        for (const p of pts) {
          if (p.z >= 0 !== isFront) {
            flush();
            isFront = p.z >= 0;
          }
          run.push(p);
        }
        flush();
      };

      ctx.lineWidth = 1;
      for (const o of ORBITS) {
        const pts: { x: number; y: number; z: number }[] = [];
        for (let i = 0; i <= 180; i++) {
          const nu = (i / 180) * Math.PI * 2;
          const r =
            (o.a * (1 - o.eccentricity ** 2)) / (1 + o.eccentricity * Math.cos(nu));
          let p: V3 = [r * Math.cos(nu), 0, r * Math.sin(nu)];
          p = rotX(p, o.inc);
          p = rotY(p, o.raan + spin * 0.3);
          const [x, y, z] = rotX(p, TILT);
          pts.push({ x: cx + x * R, y: cy - y * R, z });
        }
        strokeSplit(pts, "rgba(255,59,48,0.5)", "rgba(255,59,48,0.13)");

        const nu = o.phase + t * o.rate * Math.PI * 2;
        const r =
          (o.a * (1 - o.eccentricity ** 2)) / (1 + o.eccentricity * Math.cos(nu));
        let sp: V3 = [r * Math.cos(nu), 0, r * Math.sin(nu)];
        sp = rotX(sp, o.inc);
        sp = rotY(sp, o.raan + spin * 0.3);
        const [px3, py3, pz3] = rotX(sp, TILT);
        const px = cx + px3 * R;
        const py = cy - py3 * R;

        ctx.beginPath();
        ctx.arc(px, py, pz3 >= 0 ? 2.2 : 1.4, 0, Math.PI * 2);
        ctx.fillStyle = pz3 >= 0 ? "#ff5a50" : "rgba(255,59,48,0.3)";
        ctx.fill();

        if (pz3 >= 0) {
          const len = Math.hypot(px3, py3, pz3) || 1;
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.lineTo(cx + (px3 / len) * R, cy - (py3 / len) * R);
          ctx.strokeStyle = "rgba(255,59,48,0.14)";
          ctx.stroke();
        }
      }

      if (!stopped && !reduce) {
        raf = requestAnimationFrame(() => draw(performance.now() / 1000));
      }
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
  }, [land]);

  return (
    <canvas
      ref={ref}
      className={className}
      role="img"
      aria-label="Earth seen from orbit, with five satellite tracks and the Assam area of interest marked."
      style={{ width: "100%", height: "100%", display: "block" }}
    />
  );
}
