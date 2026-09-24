"use client";

/**
 * The landing page.
 *
 * Its job is the first ten seconds on a projector: say what this is, show that it
 * is spatial and operational, and get out of the way. The globe is the subject;
 * everything else is thin type pinned to the edges, revealed in sequence so the
 * eye is led rather than presented with a wall.
 *
 * No marketing copy, no feature grid, no testimonials. The one action is entering
 * the console.
 */

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

import { BootReadout, Counter } from "./BootReadout";
import { Label } from "../system/primitives";
import { OrbitalGlobe } from "./OrbitalGlobe";

/**
 * Typed reveal. Stepped rather than faded, because a character-by-character
 * reveal reads as a system printing a line, which is the tone; a fade reads as a
 * marketing site.
 */
function Typed({ text, delay = 0 }: { text: string; delay?: number }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(reduce ? text.length : 0);

  useEffect(() => {
    if (reduce) {
      setShown(text.length);
      return;
    }
    let i = 0;
    let id: ReturnType<typeof setTimeout>;
    const start = setTimeout(function step() {
      i += 1;
      setShown(i);
      if (i < text.length) id = setTimeout(step, 18);
    }, delay);
    return () => {
      clearTimeout(start);
      clearTimeout(id);
    };
  }, [text, delay, reduce]);

  return (
    <span>
      {text.slice(0, shown)}
      {shown < text.length ? <span className="sig blink">▌</span> : null}
    </span>
  );
}

function Reveal({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: reduce ? 0 : delay, duration: 0.4, ease: [0.2, 0, 0.1, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** Real figures from the ML evaluation, so the landing page cites nothing invented. */
const FACTS: { k: string; v: string; note: string }[] = [
  { k: "Held-out IoU", v: "0.435", note: "India + Somalia, regions never trained on" },
  { k: "Classical baseline", v: "0.204", note: "Otsu log-ratio thresholding" },
  { k: "Hand-labelled chips", v: "400", note: "Sen1Floods11, 10 regions" },
];

export default function LandingPage() {
  return (
    <div
      style={{
        position: "relative",
        height: "100dvh",
        overflow: "hidden",
        background: "var(--void)",
      }}
    >
      {/* Globe — the subject, centred and full-bleed behind the type. */}
      <div style={{ position: "absolute", inset: 0 }}>
        <OrbitalGlobe />
      </div>

      {/* Faint measurement grid, as in an instrument readout. */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.022) 1px, transparent 1px)," +
            "linear-gradient(90deg, rgba(255,255,255,0.022) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          pointerEvents: "none",
        }}
      />

      {/* Top band */}
      <div
        className="band"
        style={{ position: "absolute", top: 0, left: 0, right: 0, background: "transparent" }}
      >
        <Reveal>
          <div className="row" style={{ gap: 14 }}>
            <Label>Satellite Intelligence</Label>
            <Label faint>X-1</Label>
          </div>
        </Reveal>
        <div className="band-spacer" />
        <Reveal delay={0.1}>
          <span
            className="heading"
            style={{ fontSize: 13, letterSpacing: "0.24em", fontWeight: 700 }}
          >
            SATQUERY
          </span>
        </Reveal>
        <div className="band-spacer" />
        <Reveal delay={0.2}>
          <Link href="/dashboard" className="label" style={{ color: "var(--ink)" }}>
            MISSION CONSOLE →
          </Link>
        </Reveal>
      </div>

      {/* Left column — the claim */}
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: "min(38vw, 460px)",
          padding: "88px 0 64px 24px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          gap: 22,
          pointerEvents: "none",
        }}
      >
        <Reveal delay={0.3}>
          <Label>Mission brief</Label>
          <h1
            className="heading"
            style={{
              fontSize: "clamp(26px, 3.2vw, 44px)",
              lineHeight: 1.12,
              margin: "8px 0 0",
              fontWeight: 700,
              letterSpacing: "-0.02em",
            }}
          >
            Ask a question.
            <br />
            Get an answer
            <br />
            <span className="sig">with its evidence.</span>
          </h1>
        </Reveal>

        <Reveal delay={0.5}>
          <p
            className="mono"
            style={{
              margin: 0,
              fontSize: 11.5,
              lineHeight: 1.7,
              color: "var(--ink-dim)",
              maxWidth: 380,
            }}
          >
            <Typed
              text="Flood mapping from Sentinel-1 radar. Radar sees through cloud, and floods come with cloud."
              delay={900}
            />
          </p>
        </Reveal>

        <Reveal delay={0.8}>
          <div style={{ pointerEvents: "auto" }}>
            <Link href="/dashboard" className="btn btn-primary" style={{ height: 34 }}>
              Enter mission console
            </Link>
          </div>
        </Reveal>
      </div>

      {/* Right column — measured figures, not claims */}
      <div
        style={{
          position: "absolute",
          right: 24,
          top: "50%",
          transform: "translateY(-50%)",
          width: 300,
          maxHeight: "calc(100dvh - 120px)",
          overflowY: "auto",
          pointerEvents: "none",
        }}
      >
        <Reveal delay={1.0}>
          <Label faint>Measured performance</Label>
          <div style={{ marginTop: 8 }}>
            {FACTS.map((f, i) => (
              <div
                key={f.k}
                style={{
                  padding: "8px 0",
                  borderTop: i === 0 ? "1px solid var(--hairline)" : "none",
                  borderBottom: "1px solid var(--hairline)",
                }}
              >
                <div className="readout" style={{ padding: 0 }}>
                  <Label faint>{f.k}</Label>
                  <span className="counter" style={{ fontSize: 15 }}>
                    {f.v}
                  </span>
                </div>
                <p
                  className="mono faint"
                  style={{ margin: "1px 0 0", fontSize: 9.5, lineHeight: 1.4 }}
                >
                  {f.note}
                </p>
              </div>
            ))}
          </div>
          <p
            className="mono faint"
            style={{ margin: "8px 0 0", fontSize: 9, lineHeight: 1.5 }}
          >
            Intersection-over-union on whole held-out regions. Accuracy is not quoted:
            water is 11% of pixels, so predicting none scores 89%.
          </p>
        </Reveal>

        <div style={{ marginTop: 22 }}>
          <Reveal delay={1.15}>
            <BootReadout />
          </Reveal>
        </div>
      </div>

      {/* Bottom band */}
      <div
        className="band band-footer"
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          background: "transparent",
          height: 30,
        }}
      >
        <Reveal delay={1.2}>
          <div className="row" style={{ gap: 16 }}>
            <span className="row" style={{ gap: 6 }}>
              <Label faint>Observations indexed</Label>
              <span className="mono dim" style={{ fontSize: 10 }}>
                <Counter to={4784} delay={1.4} />
              </span>
            </span>
            <Pair k="Constellation" v="SENTINEL-1 · SENTINEL-2" />
          </div>
        </Reveal>
        <div className="band-spacer" />
        <Reveal delay={1.3}>
          <Label faint>SIH 2026 · EPSG:4326</Label>
        </Reveal>
      </div>
    </div>
  );
}

function Pair({ k, v }: { k: string; v: string }) {
  return (
    <span className="row" style={{ gap: 6 }}>
      <Label faint>{k}</Label>
      <span className="mono dim" style={{ fontSize: 10 }}>
        {v}
      </span>
    </span>
  );
}
