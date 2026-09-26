"use client";

/**
 * Glitter warp: a starfield flying out of a vanishing point, with glittering
 * particles, behind the "How it works" stage.
 *
 * Written for this page, after the React Bits Pro "Glitter Warp" (a starfield warp
 * tunnel with glittering particles), which needs a paid licence. Stars live in a
 * 3D box and move toward the viewer; each is drawn as a short streak from where it
 * was to where it is, so speed reads as length. A few in every hundred twinkle and
 * flare into a four-point glint. Colours are the page tokens: mostly white and
 * slate, with the signal orange and the two data colours only on the glints.
 *
 * `pulse` is a number the parent changes when something happens (a new step); each
 * change kicks the warp into a short burst of speed that eases back to cruising.
 *
 * Cost: one canvas, a few hundred strokes a frame, paused offscreen and in hidden
 * tabs, DPR capped at 2, one still frame under reduced motion.
 */

import { useEffect, useRef } from "react";

import { mulberry32, prefersReducedMotion } from "./canvas";

const GLINT = ["#f87010", "#60a0f8", "#30d098", "#ecedee"];
const CRUISE = 0.22; // depth units per second
const BURST = 2.4;

interface Star {
  x: number;
  y: number;
  z: number;
  pz: number;
  tw: number; // twinkle phase
  glint: number; // -1 = plain star, else index into GLINT
}

export function GlitterWarp({
  className,
  pulse = 0,
}: {
  className?: string;
  pulse?: number;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const kick = useRef(0);

  // A new pulse value = a burst. Stored as a timestamp the loop reads.
  useEffect(() => {
    kick.current = performance.now();
  }, [pulse]);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const reduced = prefersReducedMotion();
    const rand = mulberry32(31);

    let w = 0;
    let h = 0;
    let stars: Star[] = [];
    let raf = 0;
    let last = performance.now();
    let onScreen = true;

    const spawn = (s: Star, far: boolean) => {
      s.x = (rand() * 2 - 1) * 1.2;
      s.y = (rand() * 2 - 1) * 1.2;
      s.z = far ? 0.6 + rand() * 0.4 : 0.05 + rand() * 0.95;
      s.pz = s.z;
      s.tw = rand() * Math.PI * 2;
      s.glint = rand() < 0.06 ? Math.floor(rand() * GLINT.length) : -1;
    };

    const size = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const n = Math.round(Math.min(700, Math.max(220, (w * h) / 2600)));
      stars = Array.from({ length: n }, () => {
        const s = { x: 0, y: 0, z: 0, pz: 0, tw: 0, glint: -1 };
        spawn(s, false);
        return s;
      });
    };

    const draw = (now: number) => {
      raf = 0;
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;
      const since = (now - kick.current) / 1000;
      const speed =
        CRUISE +
        (BURST - CRUISE) * Math.exp(-since * 2.2) * (since >= 0 ? 1 : 0);
      const t = now / 1000;

      ctx.clearRect(0, 0, w, h);
      const cx = w / 2;
      const cy = h / 2;
      const f = Math.min(w, h) * 0.55;

      ctx.lineCap = "round";
      for (const s of stars) {
        s.pz = s.z;
        if (!reduced) s.z -= speed * dt;
        if (s.z <= 0.02) {
          spawn(s, true);
          continue;
        }
        const x = cx + (s.x / s.z) * f;
        const y = cy + (s.y / s.z) * f;
        if (x < -40 || x > w + 40 || y < -40 || y > h + 40) {
          spawn(s, true);
          continue;
        }
        const px = cx + (s.x / s.pz) * f;
        const py = cy + (s.y / s.pz) * f;
        const near = 1 - s.z; // 0 far .. 1 close
        const twinkle = 0.55 + 0.45 * Math.sin(t * 3.1 + s.tw);
        const a = Math.min(1, near * 1.2) * (s.glint >= 0 ? twinkle : 0.75);
        const width = 0.4 + near * 1.8;

        ctx.strokeStyle =
          s.glint >= 0
            ? GLINT[s.glint]!
            : near > 0.6
              ? `rgba(236,237,238,${a})`
              : `rgba(152,160,168,${a})`;
        ctx.globalAlpha = s.glint >= 0 ? a : 1;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(x, y);
        ctx.stroke();

        // glitter: a four-point glint on the brightest twinkling particles
        if (s.glint >= 0 && twinkle > 0.8 && near > 0.35) {
          const r = (2 + near * 6) * (twinkle - 0.8) * 5;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(x - r, y);
          ctx.lineTo(x + r, y);
          ctx.moveTo(x, y - r);
          ctx.lineTo(x, y + r);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }

      if (!reduced && onScreen && !document.hidden)
        raf = requestAnimationFrame(draw);
    };

    const start = () => {
      if (raf || reduced) return;
      last = performance.now();
      raf = requestAnimationFrame(draw);
    };

    size();
    draw(performance.now());
    start();

    const ro = new ResizeObserver(() => {
      size();
      if (reduced) draw(performance.now());
    });
    ro.observe(canvas);
    const io = new IntersectionObserver(([e]) => {
      onScreen = Boolean(e?.isIntersecting);
      if (onScreen) start();
    });
    io.observe(canvas);
    const vis = () => {
      if (!document.hidden) start();
    };
    document.addEventListener("visibilitychange", vis);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", vis);
    };
  }, []);

  return <canvas ref={ref} aria-hidden="true" className={className} />;
}
