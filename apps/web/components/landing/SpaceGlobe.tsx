"use client";

/**
 * The Earth, interactive, with the model's training story drawn on it.
 *
 * The planet itself is unchanged from the previous landing page and keeps its real
 * colours: Natural Earth 1:50m coastlines, orthographically projected and lit from a
 * fixed sun, with an atmospheric limb and a night side. What is new is on top of it:
 *
 *   - Ten markers, one per Sen1Floods11 region in reports/evaluation.md. Ice for the
 *     eight the model trained on, violet for the two it never saw (India, Somalia),
 *     and a coral beacon on the Assam floodplain the console's demo analyses.
 *   - Arcs from each training region to India, rising off the surface and drawn as
 *     travelling light: learned there, tested here. The arcs are the story, not data
 *     -- nothing moves between those places -- and the legend says so.
 *   - Hover a marker for its row of the evaluation table: chips, split, IoU against
 *     the baseline. Drag to spin, arrow keys to spin, and it resumes on its own.
 *
 * Points on the far side are culled before drawing -- d3's projection() returns
 * screen coordinates for them happily, and only geoPath clips. Elevated arc points
 * are culled differently: behind the planet only if they project inside the disc.
 */

import {
  geoDistance,
  geoGraticule10,
  geoInterpolate,
  geoOrthographic,
  geoPath,
  geoRotation,
} from "d3-geo";
import type { Feature, FeatureCollection, MultiPolygon, Polygon, Position } from "geojson";
import { useEffect, useRef, useState } from "react";
import { feature } from "topojson-client";
import type { Topology } from "topojson-specification";

import { DEMO_AOI, REGIONS, f3, type RegionResult } from "./facts";
import { prefersReducedMotion } from "./effects/canvas";

const SUN: [number, number] = [-0.42, -0.38];
const ICE = "125,211,252";
const VIOLET = "167,139,250";
const BEACON = "255,107,90";

const INDIA = REGIONS.find((r) => r.name === "India")!.at;
const ARCS = REGIONS.filter((r) => r.split === "trained").map((r, i) => ({
  from: r.at,
  to: INDIA,
  interp: geoInterpolate(r.at, INDIA),
  dist: geoDistance(r.at, INDIA),
  offset: i * 0.62,
}));

/** Three quiet orbits; the planet is the subject, not the constellation. */
const ORBITS = [
  { a: 1.2, inc: 1.71, raan: 0.4, rate: 0.05, phase: 0.2 }, // near-polar, as Sentinel-1 flies
  { a: 1.38, inc: 0.52, raan: 2.1, rate: 0.036, phase: 2.4 },
  { a: 1.11, inc: -0.9, raan: 3.6, rate: 0.061, phase: 4.2 },
];

type V3 = [number, number, number];
const rotX = ([x, y, z]: V3, a: number): V3 => [x, Math.cos(a) * y - Math.sin(a) * z, Math.sin(a) * y + Math.cos(a) * z];
const rotY = ([x, y, z]: V3, a: number): V3 => [Math.cos(a) * x + Math.sin(a) * z, y, -Math.sin(a) * x + Math.cos(a) * z];

/**
 * Thin the 1:50m coastline once, at load. It has ~60k vertices, and d3 re-projects
 * and adaptively resamples every one of them every frame -- that, not the arcs,
 * was what held the hero to a few frames a second in software rendering. At this
 * globe's size half a degree is about two pixels, so points closer than that are
 * invisible, and islands under a degree across do not survive the fill anyway.
 * 60,629 points in 1,421 rings become 12,857 in 262.
 */
function thin(fc: FeatureCollection, minDeg = 0.45, minExtent = 1.0): FeatureCollection {
  const ring = (r: Position[]): Position[] | null => {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [x, y] of r) {
      if (x! < minX) minX = x!;
      if (x! > maxX) maxX = x!;
      if (y! < minY) minY = y!;
      if (y! > maxY) maxY = y!;
    }
    if (maxX - minX < minExtent && maxY - minY < minExtent) return null;
    const out: Position[] = [r[0]!];
    let [lx, ly] = r[0]! as [number, number];
    for (let i = 1; i < r.length - 1; i++) {
      const [x, y] = r[i]! as [number, number];
      if (Math.abs(x - lx) + Math.abs(y - ly) >= minDeg) {
        out.push(r[i]!);
        lx = x;
        ly = y;
      }
    }
    out.push(r[r.length - 1]!);
    return out.length >= 4 ? out : null;
  };
  const poly = (rings: Position[][]) => {
    const outer = ring(rings[0]!);
    if (!outer) return null;
    return [outer, ...rings.slice(1).map(ring).filter((x): x is Position[] => x !== null)];
  };
  const features = fc.features
    .map((f): Feature | null => {
      const g = f.geometry;
      if (g.type === "Polygon") {
        const c = poly(g.coordinates);
        return c ? { ...f, geometry: { type: "Polygon", coordinates: c } as Polygon } : null;
      }
      if (g.type === "MultiPolygon") {
        const c = g.coordinates.map(poly).filter((x): x is Position[][] => x !== null);
        return c.length ? { ...f, geometry: { type: "MultiPolygon", coordinates: c } as MultiPolygon } : null;
      }
      return f;
    })
    .filter((f): f is Feature => f !== null);
  return { type: "FeatureCollection", features };
}

interface Hit {
  x: number;
  y: number;
  region: RegionResult | null; // null = the demo AOI
}

export function SpaceGlobe({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [land, setLand] = useState<FeatureCollection | null>(null);
  const [hover, setHover] = useState<Hit | null>(null);
  const hits = useRef<Hit[]>([]);
  const view = useRef({ lambda: -62, phi: -20, vx: 0, vy: 0, dragging: false, idleSince: 0 });

  useEffect(() => {
    let live = true;
    fetch("/geo/land-50m.json")
      .then((r) => r.json())
      .then((topo: Topology) => {
        if (live) setLand(thin(feature(topo, topo.objects.land!) as unknown as FeatureCollection));
      })
      // Without coastlines the globe still draws ocean, graticule, markers and
      // arcs. A landing page that fails because one asset 404'd is worse.
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduced = prefersReducedMotion();
    let raf = 0;
    let stopped = false;
    let onScreen = true;
    const start = performance.now();
    let last = start;

    const size = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * dpr));
      canvas.height = Math.max(1, Math.round(canvas.clientHeight * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    // The lit ocean, the halo, the terminator and the limb depend only on size and
    // sun direction, never on rotation. Five full-disc radial-gradient fills per
    // frame were most of the remaining cost; now they are two blits.
    let cache: { key: string; under: HTMLCanvasElement; over: HTMLCanvasElement } | null = null;
    const lighting = (w: number, h: number, cx: number, cy: number, R: number, sx: number, sy: number) => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const key = `${w}x${h}@${dpr}`;
      if (cache?.key === key) return cache;
      const mk = () => {
        const c = document.createElement("canvas");
        c.width = Math.max(1, Math.round(w * dpr));
        c.height = Math.max(1, Math.round(h * dpr));
        const x = c.getContext("2d")!;
        x.scale(dpr, dpr);
        return [c, x] as const;
      };
      const [under, u] = mk();
      const halo = u.createRadialGradient(cx, cy, R * 0.96, cx, cy, R * 1.22);
      halo.addColorStop(0, "rgba(74,158,255,0.26)");
      halo.addColorStop(0.4, "rgba(74,158,255,0.09)");
      halo.addColorStop(1, "rgba(74,158,255,0)");
      u.beginPath();
      u.arc(cx, cy, R * 1.22, 0, Math.PI * 2);
      u.fillStyle = halo;
      u.fill();
      const ocean = u.createRadialGradient(sx, sy, R * 0.05, cx, cy, R * 1.45);
      ocean.addColorStop(0, "#1d4f80");
      ocean.addColorStop(0.32, "#123553");
      ocean.addColorStop(0.62, "#0a1e33");
      ocean.addColorStop(1, "#02060c");
      u.beginPath();
      u.arc(cx, cy, R, 0, Math.PI * 2);
      u.fillStyle = ocean;
      u.fill();

      const [over, o] = mk();
      const night = o.createRadialGradient(sx, sy, R * 0.25, cx, cy, R * 1.5);
      night.addColorStop(0, "rgba(0,0,0,0)");
      night.addColorStop(0.55, "rgba(0,0,0,0.1)");
      night.addColorStop(0.85, "rgba(0,0,0,0.5)");
      night.addColorStop(1, "rgba(0,0,0,0.85)");
      o.beginPath();
      o.arc(cx, cy, R, 0, Math.PI * 2);
      o.fillStyle = night;
      o.fill();
      const rim = o.createRadialGradient(cx, cy, R * 0.9, cx, cy, R);
      rim.addColorStop(0, "rgba(120,190,255,0)");
      rim.addColorStop(1, "rgba(120,190,255,0.32)");
      o.beginPath();
      o.arc(cx, cy, R, 0, Math.PI * 2);
      o.fillStyle = rim;
      o.fill();

      cache = { key, under, over };
      return cache;
    };

    const draw = (now: number) => {
      // rAF timestamps are the frame's start time and can precede the performance.now()
      // taken when the loop was scheduled, so clamp: a negative t indexes arrays negatively.
      const t = reduced ? 0 : Math.max(0, (now - start) / 1000);
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;
      const v = view.current;

      // Spin: inertia after a drag, then ease back into the slow auto-rotation.
      if (!v.dragging && !reduced) {
        v.lambda += v.vx * dt * 60;
        v.phi = Math.max(-55, Math.min(55, v.phi + v.vy * dt * 60));
        v.vx *= 0.94;
        v.vy *= 0.94;
        const idle = (now - v.idleSince) / 1000;
        const blend = Math.min(1, Math.max(0, (idle - 1.4) / 1.6));
        v.lambda += 3.2 * dt * blend;
      }

      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      // Sit a little high so the model-card strip below only overlaps the south
      // polar limb, which rotation never brings anything interesting into.
      const cx = w / 2;
      const cy = h * 0.44;
      const R = Math.min(w, h) * 0.39;
      ctx.clearRect(0, 0, w, h);

      const projection = geoOrthographic().scale(R).translate([cx, cy]).rotate([v.lambda, v.phi, 0]).clipAngle(90).precision(1.2);
      const path = geoPath(projection, ctx);
      const rotate = geoRotation([v.lambda, v.phi, 0]);
      const centre: [number, number] = [-v.lambda, -v.phi];
      const sx = cx + SUN[0] * R;
      const sy = cy + SUN[1] * R;

      /* atmosphere + ocean: independent of rotation, so rendered once per size */
      const layers = lighting(w, h, cx, cy, R, sx, sy);
      ctx.drawImage(layers.under, 0, 0, w, h);

      /* land */
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
        ctx.strokeStyle = "rgba(150,200,255,0.18)";
        ctx.stroke();
        ctx.restore();
      }

      /* graticule */
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.clip();
      ctx.beginPath();
      path(geoGraticule10());
      ctx.lineWidth = 0.5;
      ctx.strokeStyle = "rgba(255,255,255,0.05)";
      ctx.stroke();
      ctx.restore();

      /* night side + inner rim: also rotation-independent */
      ctx.drawImage(layers.over, 0, 0, w, h);

      /* arcs: learned there, tested here */
      const lift = (p: [number, number], k: number) => {
        const [lon, lat] = rotate(p).map((d) => (d * Math.PI) / 180) as [number, number];
        const x = Math.cos(lat) * Math.sin(lon);
        const y = Math.sin(lat);
        const z = Math.cos(lat) * Math.cos(lon);
        const visible = z >= 0 || k * Math.hypot(x, y) >= 1;
        return { x: cx + R * k * x, y: cy - R * k * y, visible };
      };

      const PERIOD = 5.6;
      ctx.lineCap = "round";
      for (const arc of ARCS) {
        const hMax = 0.06 + 0.24 * (arc.dist / Math.PI);
        const SEG = 44;
        const pts = Array.from({ length: SEG + 1 }, (_, i) => {
          const s = i / SEG;
          return { s, ...lift(arc.interp(s), 1 + hMax * Math.sin(Math.PI * s)) };
        });

        // faint full arc
        ctx.lineWidth = 0.8;
        ctx.strokeStyle = `rgba(${ICE},0.16)`;
        ctx.beginPath();
        let pen = false;
        for (const p of pts) {
          if (!p.visible) {
            pen = false;
            continue;
          }
          if (!pen) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
          pen = true;
        }
        ctx.stroke();

        // travelling light
        const phase = reduced ? 0.7 : ((t + arc.offset) % PERIOD) / PERIOD;
        const head = Math.min(1, phase * 1.5);
        const fadeOut = phase > 0.66 ? 1 - (phase - 0.66) / 0.34 : 1;
        const tail = 0.35;
        for (let i = 1; i < pts.length; i++) {
          const a = pts[i - 1]!;
          const b = pts[i]!;
          if (!a.visible || !b.visible || b.s > head || b.s < head - tail) continue;
          const k = 1 - (head - b.s) / tail;
          ctx.strokeStyle = `rgba(${ICE},${0.95 * k * fadeOut})`;
          ctx.lineWidth = 1 + 1.8 * k;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        const hp = pts[Math.max(0, Math.min(SEG, Math.round(head * SEG)))]!;
        if (hp.visible && head < 1 && fadeOut > 0) {
          const g = ctx.createRadialGradient(hp.x, hp.y, 0, hp.x, hp.y, 7);
          g.addColorStop(0, `rgba(224,242,254,${0.95 * fadeOut})`);
          g.addColorStop(1, `rgba(${ICE},0)`);
          ctx.fillStyle = g;
          ctx.fillRect(hp.x - 7, hp.y - 7, 14, 14);
        }
      }

      /* markers */
      const found: Hit[] = [];
      const pulse = 0.5 + 0.5 * Math.sin(t * 2.4);
      for (const r of REGIONS) {
        if (geoDistance(r.at, centre) >= Math.PI / 2) continue;
        const p = projection(r.at);
        if (!p) continue;
        const col = r.split === "held-out" ? VIOLET : ICE;
        const big = r.split === "held-out";
        ctx.beginPath();
        ctx.arc(p[0], p[1], big ? 7 + pulse * 5 : 5, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${col},${big ? 0.55 - pulse * 0.35 : 0.35})`;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(p[0], p[1], big ? 3.2 : 2.4, 0, Math.PI * 2);
        ctx.fillStyle = `rgb(${col})`;
        ctx.fill();
        found.push({ x: p[0], y: p[1], region: r });
      }

      if (geoDistance(DEMO_AOI.at, centre) < Math.PI / 2) {
        const p = projection(DEMO_AOI.at);
        if (p) {
          const beat = (t * 0.8) % 1;
          ctx.beginPath();
          ctx.arc(p[0], p[1], 4 + beat * 16, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(${BEACON},${0.7 * (1 - beat)})`;
          ctx.lineWidth = 1.2;
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(p[0], p[1], 3, 0, Math.PI * 2);
          ctx.fillStyle = `rgb(${BEACON})`;
          ctx.fill();
          ctx.font = "600 9.5px 'IBM Plex Mono', ui-monospace, monospace";
          ctx.fillStyle = `rgba(${BEACON},0.95)`;
          ctx.fillText("ASSAM · DEMO AOI", p[0] + 10, p[1] - 8);
          found.push({ x: p[0], y: p[1], region: null });
        }
      }
      hits.current = found;

      /* orbits */
      const tilt = -0.36;
      const spin = (v.lambda * Math.PI) / 180;
      ctx.lineWidth = 0.8;
      for (const o of ORBITS) {
        const pts: { x: number; y: number; z: number }[] = [];
        for (let i = 0; i <= 160; i++) {
          const nu = (i / 160) * Math.PI * 2;
          let q: V3 = [o.a * Math.cos(nu), 0, o.a * Math.sin(nu)];
          q = rotX(q, o.inc);
          q = rotY(q, o.raan + spin * 0.2);
          const [x, y, z] = rotX(q, tilt);
          pts.push({ x: cx + x * R, y: cy - y * R, z });
        }
        // Batch into one front path and one back path: 160 separate strokes per
        // orbit were a measurable share of the frame.
        const front = new Path2D();
        const back = new Path2D();
        for (let i = 1; i < pts.length; i++) {
          const a = pts[i - 1]!;
          const b = pts[i]!;
          const target = b.z < 0 && Math.hypot(b.x - cx, b.y - cy) < R ? back : front;
          target.moveTo(a.x, a.y);
          target.lineTo(b.x, b.y);
        }
        ctx.strokeStyle = `rgba(${ICE},0.04)`;
        ctx.stroke(back);
        ctx.strokeStyle = `rgba(${ICE},0.22)`;
        ctx.stroke(front);
        const nu = o.phase + t * o.rate * Math.PI * 2;
        let q: V3 = [o.a * Math.cos(nu), 0, o.a * Math.sin(nu)];
        q = rotX(q, o.inc);
        q = rotY(q, o.raan + spin * 0.2);
        const [x, y, z] = rotX(q, tilt);
        const px = cx + x * R;
        const py = cy - y * R;
        const behind = z < 0 && Math.hypot(px - cx, py - cy) < R;
        if (!behind) {
          const g = ctx.createRadialGradient(px, py, 0, px, py, 6);
          g.addColorStop(0, "rgba(240,249,255,0.95)");
          g.addColorStop(1, `rgba(${ICE},0)`);
          ctx.fillStyle = g;
          ctx.fillRect(px - 6, py - 6, 12, 12);
        }
      }

      if (!stopped && !reduced && onScreen) raf = requestAnimationFrame(draw);
    };

    const kick = () => {
      cancelAnimationFrame(raf);
      last = performance.now();
      raf = requestAnimationFrame(draw);
    };

    size();
    kick();

    const ro = new ResizeObserver(() => {
      size();
      draw(performance.now());
    });
    ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => {
      const was = onScreen;
      onScreen = Boolean(e?.isIntersecting);
      if (onScreen && !was) kick();
    });
    io.observe(canvas);

    /* drag to spin */
    let lx = 0;
    let ly = 0;
    const v = view.current;
    const down = (ev: PointerEvent) => {
      v.dragging = true;
      v.vx = 0;
      v.vy = 0;
      lx = ev.clientX;
      ly = ev.clientY;
      canvas.setPointerCapture(ev.pointerId);
      canvas.style.cursor = "grabbing";
    };
    const move = (ev: PointerEvent) => {
      if (v.dragging) {
        const dx = ev.clientX - lx;
        const dy = ev.clientY - ly;
        lx = ev.clientX;
        ly = ev.clientY;
        v.lambda += dx * 0.32;
        v.phi = Math.max(-55, Math.min(55, v.phi - dy * 0.25));
        v.vx = dx * 0.32 * 0.5;
        v.vy = -dy * 0.25 * 0.5;
        if (reduced) draw(performance.now());
        return;
      }
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      let best: Hit | null = null;
      let bd = 14;
      for (const hit of hits.current) {
        const d = Math.hypot(hit.x - mx, hit.y - my);
        if (d < bd) {
          bd = d;
          best = hit;
        }
      }
      setHover(best);
      canvas.style.cursor = best ? "pointer" : "grab";
    };
    const up = (ev: PointerEvent) => {
      if (!v.dragging) return;
      v.dragging = false;
      v.idleSince = performance.now();
      canvas.releasePointerCapture?.(ev.pointerId);
      canvas.style.cursor = "grab";
    };
    const leave = () => setHover(null);
    const key = (ev: KeyboardEvent) => {
      const step = ev.shiftKey ? 30 : 10;
      if (ev.key === "ArrowLeft") v.lambda -= step;
      else if (ev.key === "ArrowRight") v.lambda += step;
      else if (ev.key === "ArrowUp") v.phi = Math.max(-55, v.phi - step);
      else if (ev.key === "ArrowDown") v.phi = Math.min(55, v.phi + step);
      else return;
      ev.preventDefault();
      v.idleSince = performance.now();
      if (reduced) draw(performance.now());
    };

    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("pointerleave", leave);
    canvas.addEventListener("keydown", key);

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up);
      canvas.removeEventListener("pointercancel", up);
      canvas.removeEventListener("pointerleave", leave);
      canvas.removeEventListener("keydown", key);
    };
  }, [land]);

  return (
    <div className={`sq-globe ${className ?? ""}`}>
      <canvas
        ref={canvasRef}
        tabIndex={0}
        role="img"
        aria-label={
          "Earth with the ten Sen1Floods11 regions marked: eight the model trained on, " +
          "India and Somalia held out, and the Assam demo area. Drag or use the arrow keys to rotate."
        }
        className="sq-globe-canvas"
      />
      {hover ? (
        <div className="sq-globe-tip" style={{ left: hover.x, top: hover.y }} role="status">
          {hover.region ? (
            <>
              <div className="sq-tip-head">
                <span className={`sq-dot ${hover.region.split === "held-out" ? "is-violet" : "is-ice"}`} />
                {hover.region.name}
                <span className="sq-tip-split">
                  {hover.region.split === "held-out" ? "held out" : "trained"}
                </span>
              </div>
              <div className="sq-tip-row">
                <span>IoU</span>
                <b>{f3(hover.region.modelIoU)}</b>
                <span className="sq-tip-vs">vs {f3(hover.region.baselineIoU)} baseline</span>
              </div>
              <div className="sq-tip-note">
                {hover.region.chips} chips ·{" "}
                {hover.region.split === "held-out"
                  ? "never seen in training"
                  : "partly recall, not generalisation"}
              </div>
            </>
          ) : (
            <>
              <div className="sq-tip-head">
                <span className="sq-dot is-beacon" />
                {DEMO_AOI.name}
              </div>
              <div className="sq-tip-note">{DEMO_AOI.detail}</div>
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
