"use client";

/**
 * Glitch headline: canvas text with a sticky glitch that follows the cursor.
 *
 * Original implementation (not the React Bits Pro source). The effect: the text is
 * cut into horizontal slices. Moving the pointer across it charges the slices near
 * the pointer with "energy"; a charged slice jumps sideways and splits into cyan and
 * magenta channels, and holds that displaced position until its energy decays --
 * that holding is what makes it feel sticky rather than jittery. With no pointer, a
 * short seeded burst fires every few seconds so the headline is never dead.
 *
 * Accessibility is not an afterthought here, it is the structure:
 *
 *   - The real heading text is in the DOM, in the heading element, always. Screen
 *     readers, find-in-page, SEO and the E2E suite read that, never the canvas.
 *   - The canvas is aria-hidden and only takes over once it has painted. Before
 *     hydration the DOM text is visible, so there is no flash of invisible heading.
 *   - prefers-reduced-motion skips the canvas entirely and shows the DOM text,
 *     gradient included, via background-clip.
 *
 * Font size is fitted, not guessed: the widest line is measured and the size chosen
 * so it fits the container on one line, clamped to [minSize, maxSize]. Lines are
 * explicit so the canvas never has to reproduce browser word-wrapping.
 */

import { createElement, useEffect, useLayoutEffect, useRef, useState } from "react";

import { mulberry32, prefersReducedMotion } from "./canvas";

export interface GlitchLine {
  text: string;
  tone?: "solid" | "gradient";
}

interface Props {
  lines: GlitchLine[];
  as?: "h1" | "h2" | "p";
  minSize?: number;
  maxSize?: number;
  weight?: number;
  lineHeight?: number;
  className?: string;
  /** Seed for the ambient bursts, so two headlines on a page do not fire in sync. */
  seed?: number;
}

const GRADIENT: [number, string][] = [
  [0, "#7dd3fc"],
  [0.55, "#a78bfa"],
  [1, "#f0abfc"],
];
const SOLID = "#eef1ff";
const FAMILY = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif";

// useLayoutEffect warns during SSR; this is the standard isomorphic guard.
const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

export function GlitchText({
  lines,
  as = "h1",
  minSize = 30,
  maxSize = 78,
  weight = 800,
  lineHeight = 1.06,
  className,
  seed = 7,
}: Props) {
  const wrapRef = useRef<HTMLElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [fontSize, setFontSize] = useState(maxSize);
  const [live, setLive] = useState(false);
  const [reduced, setReduced] = useState(false);

  /* ── fit the widest line to the container ──────────────────────────────── */

  useIsoLayoutEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    setReduced(prefersReducedMotion());
    const probe = document.createElement("canvas").getContext("2d");
    if (!probe) return;

    const fit = () => {
      const avail = wrap.parentElement?.clientWidth ?? wrap.clientWidth;
      probe.font = `${weight} 100px ${FAMILY}`;
      const widest = Math.max(...lines.map((l) => probe.measureText(l.text).width));
      // -0.02em tracking is applied when drawing; account for it here too.
      const perPx = (widest - 0.02 * 100 * Math.max(...lines.map((l) => l.text.length))) / 100;
      const size = Math.floor(avail / Math.max(perPx, 0.01)) - 1;
      setFontSize(Math.max(minSize, Math.min(maxSize, size)));
    };

    fit();
    const ro = new ResizeObserver(fit);
    if (wrap.parentElement) ro.observe(wrap.parentElement);
    document.fonts?.ready.then(fit).catch(() => undefined);
    return () => ro.disconnect();
  }, [lines, minSize, maxSize, weight]);

  /* ── the glitch loop ───────────────────────────────────────────────────── */

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas || prefersReducedMotion()) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rand = mulberry32(seed);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const lh = fontSize * lineHeight;
    const W = Math.ceil(wrap.clientWidth);
    const H = Math.ceil(lh * lines.length);
    const pad = Math.ceil(fontSize * 0.4); // room for slices to jump sideways
    const CW = W + pad * 2;

    canvas.width = CW * dpr;
    canvas.height = H * dpr;
    canvas.style.width = `${CW}px`;
    canvas.style.height = `${H}px`;
    canvas.style.left = `${-pad}px`;
    ctx.setTransform(1, 0, 0, 1, 0, 0);

    /* Three pre-rendered copies: clean, cyan channel, magenta channel. */
    const layer = (fill: (l: GlitchLine, c: CanvasRenderingContext2D, w: number) => string | CanvasGradient) => {
      const c = document.createElement("canvas");
      c.width = CW * dpr;
      c.height = H * dpr;
      const x = c.getContext("2d")!;
      x.scale(dpr, dpr);
      x.font = `${weight} ${fontSize}px ${FAMILY}`;
      x.textBaseline = "middle";
      if ("letterSpacing" in x) (x as unknown as { letterSpacing: string }).letterSpacing = `${-0.02 * fontSize}px`;
      lines.forEach((l, i) => {
        const w = x.measureText(l.text).width;
        x.fillStyle = fill(l, x, w);
        x.fillText(l.text, pad, i * lh + lh / 2);
      });
      return c;
    };

    const clean = layer((l, x, w) => {
      if (l.tone !== "gradient") return SOLID;
      const g = x.createLinearGradient(pad, 0, pad + w, 0);
      GRADIENT.forEach(([s, c]) => g.addColorStop(s, c));
      return g;
    });
    const cyan = layer(() => "rgba(34,211,238,0.9)");
    const magenta = layer(() => "rgba(240,80,220,0.9)");

    const slice = Math.max(3, Math.round(fontSize * 0.075));
    const rows = Math.ceil(H / slice);
    const energy = new Float32Array(rows);
    const offset = new Float32Array(rows);

    let raf = 0;
    let running = false;
    let last = performance.now();
    let burstUntil = 0;
    let burstRows: number[] = [];

    const paint = (dt: number, now: number) => {
      const decay = Math.exp(-dt / 0.45);
      let active = false;

      if (now < burstUntil) {
        for (const r of burstRows) energy[r] = Math.max(energy[r]!, 0.85);
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let r = 0; r < rows; r++) {
        const e = energy[r]! * (dt > 0 ? decay : 1);
        energy[r] = e < 0.012 ? 0 : e;
        if (energy[r]! > 0) active = true;

        // Sticky: a charged slice only occasionally picks a new position, and
        // otherwise holds where it jumped to.
        if (energy[r]! > 0.05 && rand() < energy[r]! * 0.3) {
          offset[r] = (rand() * 2 - 1) * fontSize * 0.32 * energy[r]!;
        } else if (energy[r] === 0) {
          offset[r] = 0;
        }

        const sy = r * slice * dpr;
        const sh = Math.min(slice * dpr, canvas.height - sy);
        if (sh <= 0) continue;
        const dx = offset[r]! * dpr;
        ctx.globalCompositeOperation = "source-over";
        ctx.globalAlpha = 1;
        ctx.drawImage(clean, 0, sy, canvas.width, sh, dx, sy, canvas.width, sh);

        if (energy[r]! > 0.18) {
          const split = fontSize * 0.06 * energy[r]! * dpr;
          ctx.globalCompositeOperation = "lighter";
          ctx.globalAlpha = Math.min(1, energy[r]! * 0.9);
          ctx.drawImage(cyan, 0, sy, canvas.width, sh, dx - split, sy, canvas.width, sh);
          ctx.drawImage(magenta, 0, sy, canvas.width, sh, dx + split, sy, canvas.width, sh);
        }
      }
      ctx.globalCompositeOperation = "source-over";
      ctx.globalAlpha = 1;
      return active || now < burstUntil;
    };

    const loop = (now: number) => {
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000));
      last = now;
      if (paint(dt, now)) {
        raf = requestAnimationFrame(loop);
      } else {
        running = false;
      }
    };
    const wake = () => {
      if (running) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(loop);
    };

    paint(0, performance.now());
    setLive(true);

    /* Cursor charges the slices it passes over. */
    let px = -1;
    let py = -1;
    const onMove = (ev: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const y = ev.clientY - rect.top;
      const inside = x > -30 && x < rect.width + 30 && y > -30 && y < rect.height + 30;
      if (inside && px >= 0) {
        const speed = Math.hypot(x - px, y - py);
        const row = Math.floor(y / slice);
        const charge = Math.min(1, speed / 26);
        for (let k = -3; k <= 3; k++) {
          const r = row + k;
          if (r < 0 || r >= rows) continue;
          energy[r] = Math.min(1, energy[r]! + charge * (1 - Math.abs(k) / 4));
        }
        if (charge > 0.02) wake();
      }
      px = x;
      py = y;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    /* Ambient bursts on a seeded schedule, so the headline is never static. */
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(() => {
        if (document.visibilityState === "visible") {
          const n = 2 + Math.floor(rand() * 3);
          const centre = Math.floor(rand() * rows);
          burstRows = Array.from({ length: n }, (_, i) => Math.min(rows - 1, centre + i));
          burstUntil = performance.now() + 140 + rand() * 180;
          wake();
        }
        schedule();
      }, 2600 + rand() * 3400);
    };
    schedule();

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
      window.removeEventListener("pointermove", onMove);
    };
  }, [fontSize, lines, lineHeight, weight, seed]);

  const showDom = !live || reduced;

  return createElement(
    as,
    {
      ref: wrapRef,
      className: `sq-glitch ${className ?? ""}`,
      style: {
        fontSize,
        lineHeight,
        fontWeight: weight,
        height: Math.ceil(fontSize * lineHeight * lines.length),
      },
    },
    lines.map((l, i) => (
      <span
        key={i}
        className={`sq-glitch-line${l.tone === "gradient" ? " sq-glitch-gradient" : ""}`}
        style={showDom ? undefined : { color: "transparent", WebkitTextFillColor: "transparent", background: "none" }}
      >
        {l.text}
      </span>
    )),
    reduced ? null : <canvas key="c" ref={canvasRef} aria-hidden="true" className="sq-glitch-canvas" />,
  );
}
