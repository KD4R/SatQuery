"use client";

/** Small shared pieces for the landing sections. */

import { animate, motion, useInView, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

/** Fade-and-rise once, when scrolled into view. */
export function Reveal({
  children,
  delay = 0,
  y = 18,
  className,
  as = "div",
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
  className?: string;
  as?: "div" | "li" | "article";
}) {
  const reduce = useReducedMotion();
  const Tag = motion[as];
  return (
    <Tag
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ delay: reduce ? 0 : delay, duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </Tag>
  );
}

/**
 * Counts up to `to` the first time it scrolls into view. Server-renders the final
 * value, so the number is right with JavaScript off and for anything reading the
 * DOM before the animation runs.
 */
export function CountUp({
  to,
  decimals = 0,
  suffix = "",
  className,
}: {
  to: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const [value, setValue] = useState(to);
  const armed = useRef(false);

  useEffect(() => {
    if (reduce || armed.current) return;
    armed.current = true;
    setValue(0);
  }, [reduce]);

  useEffect(() => {
    if (!inView || reduce) return;
    const controls = animate(0, to, {
      duration: 1.4,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: setValue,
    });
    return () => controls.stop();
  }, [inView, reduce, to]);

  return (
    <span ref={ref} className={className}>
      {value.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/* ── Icons: inline, 1.6px stroke, currentColor ──────────────────────────── */

const I = ({ children }: { children: React.ReactNode }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

export const IconCloud = () => (
  <I>
    <path d="M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.2 9.5 4.3 4.3 0 0 0 7 18Z" />
    <path d="M9 21l1.5-2M13 21l1.5-2" />
  </I>
);
export const IconMoon = () => (
  <I>
    <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />
  </I>
);
export const IconWaves = () => (
  <I>
    <path d="M3 9c2 0 2-1.5 4.5-1.5S9.5 9 12 9s2-1.5 4.5-1.5S18.5 9 21 9" />
    <path d="M3 15c2 0 2-1.5 4.5-1.5S9.5 15 12 15s2-1.5 4.5-1.5S18.5 15 21 15" />
  </I>
);
export const IconArrow = () => (
  <svg className="sq-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);
