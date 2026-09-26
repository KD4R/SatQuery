"use client";

/**
 * The hero headline.
 *
 * Static-first: with JavaScript off, reduced motion, or a screenshot taken before
 * anything runs, it is three finished lines of type with "evidence" underlined. On
 * load it plays one pass that reads as signal -> processing -> information: a
 * one-pixel scan line travels down the block, each line is unmasked as the scan
 * reaches it, and the underline under "evidence" draws last. That part is pure CSS
 * (.sq-headline in space.css), so it runs from the server HTML and can never leave
 * the headline hidden.
 *
 * Proximity glitch: after that, a line glitches only when the cursor comes near it
 * -- a chromatic split in the page's blue and signal orange, sliced and jittered,
 * scaling with distance inside a 220px radius and settling back to clean type when
 * the cursor leaves. Modelled on the React Bits Pro Glitch Text behaviour (radius-
 * based, cursor-driven), written here because that component needs a paid licence.
 * The copies are CSS pseudo-elements fed from data-glitch, so the heading's text,
 * its accessible name and what search engines read are untouched. Nothing runs on
 * touch screens or under reduced motion.
 */

import { useEffect, useRef } from "react";

const RADIUS = 220;
const STEP_MS = 70; // the slice pattern changes ~14 times a second: a glitch, not a blur

const LINES = ["Ask a question.", "Get an answer", "with its evidence."];

const line = (i: number) => ({ "--i": i }) as React.CSSProperties;

export function HeroHeadline() {
  const ref = useRef<HTMLHeadingElement | null>(null);

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
      <span className="sq-scan" aria-hidden="true" />
      <span className="sq-headline-line">
        <span style={line(0)} data-glitch={LINES[0]}>
          {LINES[0]}
        </span>
      </span>
      <span className="sq-headline-line">
        <span style={line(1)} data-glitch={LINES[1]}>
          {LINES[1]}
        </span>
      </span>
      <span className="sq-headline-line sq-headline-line--quiet">
        <span style={line(2)} data-glitch={LINES[2]}>
          with its <span className="sq-headline-mark">evidence</span>.
        </span>
      </span>
    </h1>
  );
}
