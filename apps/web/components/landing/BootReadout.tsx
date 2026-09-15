"use client";

/**
 * The boot readout (landing page).
 *
 * The reference film's most distinctive UI element: a numbered ruler where most
 * lines are empty, each populated line carrying a label, a percentage counting up,
 * and a state chip that flips to ACTIVE when it lands. The empty numerals are the
 * information — they show the shape of the whole sequence, so three completed
 * checks read as "three of twelve" rather than as a three-item list.
 *
 * Animated in React rather than CSS: each row owns its own progress state and the
 * count is driven by a Framer Motion spring, so the numerals land on exact integers
 * and the chip flips on the frame the value reaches 100. A CSS keyframe animation
 * cannot coordinate a numeral with a state change; this can.
 *
 * Text stays crisp because nothing is scaled or transformed during the count — only
 * opacity and a 3px translate, which do not resample glyphs.
 */

import {
  animate,
  motion,
  useMotionValue,
  useReducedMotion,
  useTransform,
} from "framer-motion";
import { useEffect, useState } from "react";

import { Label, StatusChip } from "../system/primitives";

interface Check {
  line: number;
  label: string;
  /** Seconds after mount that this row starts counting. */
  at: number;
  /** Where the count settles. Not every check reaches 100. */
  to: number;
}

/**
 * These are the console's real startup checks, in the order the app performs them.
 * The list is fixed, so the sequence is identical on every load — the landing page
 * has to be safe to put on a projector.
 */
const CHECKS: Check[] = [
  { line: 1, label: "Contract schema", at: 0.3, to: 100 },
  { line: 2, label: "Gateway route table", at: 0.8, to: 100 },
  { line: 4, label: "Coastline geometry", at: 1.4, to: 100 },
  { line: 5, label: "Orbital propagation", at: 1.9, to: 100 },
  { line: 8, label: "Observation index", at: 2.5, to: 100 },
  { line: 9, label: "Model — hand-only-v2", at: 3.0, to: 100 },
  { line: 11, label: "Confidence calibration", at: 3.6, to: 58 },
  { line: 12, label: "Evidence graph", at: 4.1, to: 100 },
];

const TOTAL_LINES = 14;

export function BootReadout() {
  const reduce = useReducedMotion();
  const rows = new Map(CHECKS.map((c) => [c.line, c]));

  return (
    <div style={{ width: 300 }}>
      <Label faint>System checks</Label>
      <div style={{ marginTop: 8, borderTop: "1px solid var(--hairline)" }}>
        {Array.from({ length: TOTAL_LINES }, (_, i) => {
          const n = i + 1;
          const check = rows.get(n);
          return (
            <div
              key={n}
              style={{
                display: "grid",
                gridTemplateColumns: "22px 1fr",
                minHeight: 17,
                alignItems: "center",
              }}
            >
              <span
                className="mono"
                style={{
                  fontSize: 9,
                  color: "var(--ink-ghost)",
                  textAlign: "right",
                  paddingRight: 8,
                }}
                aria-hidden="true"
              >
                {n}
              </span>
              {check ? <CheckRow check={check} reduce={Boolean(reduce)} /> : <span />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CheckRow({ check, reduce }: { check: Check; reduce: boolean }) {
  const progress = useMotionValue(reduce ? check.to : 0);
  const percent = useTransform(progress, (v) => `${Math.round(v)}%`);
  const [landed, setLanded] = useState(reduce);

  useEffect(() => {
    if (reduce) return;
    const start = setTimeout(() => {
      const controls = animate(progress, check.to, {
        duration: 0.9,
        ease: [0.16, 1, 0.3, 1],
        onComplete: () => setLanded(true),
      });
      return () => controls.stop();
    }, check.at * 1000);
    return () => clearTimeout(start);
  }, [check, progress, reduce]);

  const partial = check.to < 100;

  return (
    <motion.div
      className="row"
      initial={reduce ? false : { opacity: 0, x: 3 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: reduce ? 0 : check.at, duration: 0.25 }}
      style={{ gap: 8 }}
    >
      <span
        className="label"
        style={{ color: "var(--ink-dim)", letterSpacing: "0.1em" }}
      >
        {check.label}
      </span>
      <div className="band-spacer" />
      <motion.span
        className="mono"
        style={{
          fontSize: 10,
          color: landed && partial ? "var(--amber)" : "var(--ink)",
          minWidth: 30,
          textAlign: "right",
        }}
      >
        {percent}
      </motion.span>
      <span style={{ width: 62, display: "flex", justifyContent: "flex-end" }}>
        {landed ? (
          <StatusChip
            tone={partial ? "warn" : "active"}
            title={
              partial
                ? "Calibration did not reach the 0.05 ECE bar; results are labelled uncalibrated."
                : undefined
            }
          >
            {partial ? "Partial" : "Active"}
          </StatusChip>
        ) : null}
      </span>
    </motion.div>
  );
}

/**
 * A grouped-digit counter that ticks up to its target — the film's big numeral.
 * Tabular figures and no transform, so the digits do not jitter or blur while
 * counting.
 */
export function Counter({
  to,
  groups = 3,
  delay = 0,
}: {
  to: number;
  groups?: number;
  delay?: number;
}) {
  const reduce = useReducedMotion();
  const value = useMotionValue(reduce ? to : 0);
  const text = useTransform(value, (v) => {
    const digits = Math.max(0, Math.trunc(v)).toString().padStart(groups * 3, "0");
    return (digits.match(/.{1,3}/g) ?? [digits]).join(".");
  });

  useEffect(() => {
    if (reduce) return;
    const start = setTimeout(() => {
      const controls = animate(value, to, { duration: 1.6, ease: [0.16, 1, 0.3, 1] });
      return () => controls.stop();
    }, delay * 1000);
    return () => clearTimeout(start);
  }, [to, delay, value, reduce]);

  return <motion.span className="counter">{text}</motion.span>;
}
