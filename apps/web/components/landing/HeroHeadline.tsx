"use client";

/**
 * The headline, as a 3D scroll reveal.
 *
 * One or two words per line, set huge in a heavy expanded face. Each line is
 * upright while it sits in the lower part of the screen; as scrolling carries it
 * up past the middle it folds back on its baseline -- rotating away from the viewer
 * in perspective, flattening and greying -- until near the top it lies almost flat.
 * The effect is entirely scroll-linked, so it reverses on the way back.
 *
 * Modelled on the React Bits Pro "3D Text Reveal" (scroll-triggered, GSAP), written
 * here without GSAP because that component needs a paid licence. It is one style
 * write per line per animation frame, and only while scrolling.
 *
 * Static-first: the server HTML is the headline, upright and complete. With
 * JavaScript off or reduced motion, nothing ever tilts. The heading's text is the
 * ordinary sentence -- the capitals are CSS -- so its accessible name reads
 * normally.
 *
 * A line also glitches when the cursor comes near it (a sliced chromatic split in
 * blue and signal orange); the copies are pseudo-elements with empty alt text.
 */

import { useEffect, useRef } from "react";

const LINES = [
  "Ask a",
  "question.",
  "Get an",
  "answer",
  "with its",
  "evidence.",
];

const MAX_TILT = 82; // degrees, at the top of the viewport
const RADIUS = 220;
const STEP_MS = 70;

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

export function HeroHeadline() {
  const ref = useRef<HTMLHeadingElement | null>(null);

  /* ── scroll-linked fold ──────────────────────────────────────────────── */
  useEffect(() => {
    const h = ref.current;
    const scroller = h?.closest<HTMLElement>(".sq-landing");
    if (!h || !scroller) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const lines = Array.from(h.querySelectorAll<HTMLElement>("[data-line]"));
    let raf = 0;

    const apply = () => {
      raf = 0;
      const box = scroller.getBoundingClientRect();
      const top = box.top + 64; // below the sticky nav
      const mid = top + (box.height - 64) * 0.55;
      const span = mid - top;
      for (const el of lines) {
        const r = el.getBoundingClientRect();
        const y = r.top + r.height / 2;
        // 0 at or below the fold line, 1 at the top edge of the view
        const t = clamp01((mid - y) / span);
        const e = t * t; // slow start: a line only really folds near the top
        el.style.setProperty("--tilt", e.toFixed(3));
        el.style.transform =
          e > 0
            ? `perspective(1100px) rotateX(${(e * MAX_TILT).toFixed(2)}deg)`
            : "";
      }
    };

    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(apply);
    };
    apply();
    scroller.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      scroller.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      for (const el of lines) {
        el.style.transform = "";
        el.style.removeProperty("--tilt");
      }
    };
  }, []);

  /* ── proximity glitch ────────────────────────────────────────────────── */
  useEffect(() => {
    const h = ref.current;
    if (!h) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches)
      return;

    const els = Array.from(h.querySelectorAll<HTMLElement>("[data-glitch]"));
    const cur = new Float32Array(els.length);
    let px = -1e5;
    let py = -1e5;
    let raf = 0;
    let lastStep = 0;

    const slice = (el: HTMLElement) => {
      const a = Math.random() * 70;
      const b = Math.random() * 70;
      el.style.setProperty("--c1", `${a.toFixed(0)}%`);
      el.style.setProperty(
        "--c2",
        `${Math.max(0, 90 - a - 20 * Math.random()).toFixed(0)}%`,
      );
      el.style.setProperty("--c3", `${b.toFixed(0)}%`);
      el.style.setProperty(
        "--c4",
        `${Math.max(0, 90 - b - 20 * Math.random()).toFixed(0)}%`,
      );
      el.style.setProperty("--jx", (Math.random() * 2 - 1).toFixed(2));
    };

    const tick = (now: number) => {
      raf = 0;
      const stepNow = now - lastStep > STEP_MS;
      if (stepNow) lastStep = now;
      let busy = false;
      els.forEach((el, i) => {
        const r = el.getBoundingClientRect();
        const dx = Math.max(r.left - px, 0, px - r.right);
        const dy = Math.max(r.top - py, 0, py - r.bottom);
        const target = Math.max(0, 1 - Math.hypot(dx, dy) / RADIUS) ** 1.6;
        let v = cur[i]! + (target - cur[i]!) * 0.2;
        if (v < 0.004 && target === 0) v = 0;
        cur[i] = v;
        el.style.setProperty("--g", v.toFixed(3));
        if (v > 0 && stepNow) slice(el);
        if (v > 0 || target > 0) busy = true;
      });
      if (busy) raf = requestAnimationFrame(tick);
    };

    const wake = () => {
      if (!raf) raf = requestAnimationFrame(tick);
    };
    const onMove = (e: PointerEvent) => {
      px = e.clientX;
      py = e.clientY;
      wake();
    };
    const onLeave = () => {
      px = -1e5;
      py = -1e5;
      wake();
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, []);

  return (
    <h1 ref={ref} className="sq-headline">
      {LINES.map((line, i) => (
        <span key={line}>
          <span className="sq-headline-line" data-line="">
            <span data-glitch={line}>
              {line === "evidence." ? (
                <>
                  <span className="sq-headline-mark">evidence</span>.
                </>
              ) : (
                line
              )}
            </span>
          </span>
          {i < LINES.length - 1 ? " " : null}
        </span>
      ))}
    </h1>
  );
}
