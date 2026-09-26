"use client";

/**
 * The opening, in three beats.
 *
 *   1. Stage   -- the planet alone, as large as the screen allows, with the ten
 *                 evaluation regions on it. It spins in when the logo has landed,
 *                 and zooms past as you scroll on.
 *   2. Reveal  -- scrolling turns the headline up word by word in 3D, then the one
 *                 sentence that says how it works.
 *   3. Intro   -- what you would type (the query console), the way in, three
 *                 measured facts, and the model validation card: the numbers a judge
 *                 asks for first, each traceable to reports/evaluation.md or
 *                 reports/calibration.md.
 */

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useEffect, useRef } from "react";

import type { IntroPhase } from "../BrandIntro";

import { CALIBRATION, HEADLINE, MODEL, REGIONS, f3, ratio } from "../facts";
import { HeroHeadline } from "../HeroHeadline";
import { QueryConsole } from "../QueryConsole";
import { SpaceGlobe } from "../SpaceGlobe";
import { IconArrow, Reveal } from "../ui";

const ease = [0.16, 1, 0.3, 1] as const;

const TRAINED_REGIONS = REGIONS.filter((r) => r.split === "trained").length;
export function Hero({ phase }: { phase: IntroPhase }) {
  const reduce = useReducedMotion();
  const zoomRef = useRef<HTMLDivElement | null>(null);

  // Scrolling away from the planet zooms past it: it grows a little and fades as
  // the headline section comes up. Scroll-linked, so it reverses on the way back.
  useEffect(() => {
    const el = zoomRef.current;
    const scroller = el?.closest<HTMLElement>(".sq-landing");
    const stage = el?.closest<HTMLElement>(".sq-stage");
    if (!el || !scroller || !stage) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const apply = () => {
      raf = 0;
      const p = Math.min(
        1,
        Math.max(0, scroller.scrollTop / Math.max(1, stage.offsetHeight)),
      );
      el.style.transform = p
        ? `translate3d(0, ${(p * -40).toFixed(1)}px, 0) scale(${(1 + p * 0.18).toFixed(4)})`
        : "";
      el.style.opacity = p ? (1 - p * 1.1).toFixed(3) : "";
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(apply);
    };
    scroller.addEventListener("scroll", onScroll, { passive: true });
    apply();
    return () => {
      cancelAnimationFrame(raf);
      scroller.removeEventListener("scroll", onScroll);
    };
  }, []);

  return (
    <>
      {/* 1 ── the planet ───────────────────────────────────────────────── */}
      <section
        className="sq-stage"
        aria-label="The ten evaluation regions on a globe"
      >
        <div className="sq-stage-figure sq-intro-wait">
          <div ref={zoomRef} className="sq-stage-zoom">
            <SpaceGlobe className="sq-globe--stage" spinIn={phase === "done"} />
          </div>
        </div>
      </section>

      {/* 2 ── the headline, revealed by scroll ─────────────────────────── */}
      <section id="intro" className="sq-reveal" aria-label="Introduction">
        <div className="sq-reveal-sticky">
          <div className="sq-wrap sq-reveal-inner">
            <HeroHeadline
              lede={
                <p className="sq-lede">
                  SatQuery maps flood water from <b>Sentinel-1 radar</b>, which
                  sees through the cloud that floods arrive with — and returns
                  the evidence, the caveats, and what it could not measure.
                </p>
              }
            />
          </div>
        </div>
      </section>

      {/* 3 ── try it, and the numbers ──────────────────────────────────── */}
      <section className="sq-wrap sq-intro" aria-label="Try it">
        <div className="sq-intro-copy">
          <Reveal>
            <QueryConsole />
          </Reveal>

          <Reveal delay={0.08}>
            <div className="sq-cta-row">
              <Link href="/console" className="sq-btn sq-btn--primary">
                Enter mission console
                <IconArrow />
              </Link>
              <a href="#how" className="sq-btn sq-btn--secondary">
                <span className="sq-btn-rule">See how it works</span>
              </a>
            </div>
          </Reveal>

          <Reveal delay={0.16}>
            <div className="sq-trust">
              <div>
                <b>{ratio(HEADLINE.pooledIoU, HEADLINE.baselinePooledIoU)}</b>
                <span>the classical baseline</span>
              </div>
              <div>
                <b>{HEADLINE.heldOutChips}</b>
                <span>unseen test chips</span>
              </div>
              <div>
                <b>{HEADLINE.regionCount}</b>
                <span>flood regions</span>
              </div>
            </div>
          </Reveal>
        </div>

        <motion.aside
          className="sq-validation"
          aria-label="Model card"
          initial={reduce ? false : { opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.8, ease }}
        >
          <div className="sq-validation-head">
            <span className="sq-label">Model validation</span>
            <span className="sq-validation-source">reports/evaluation.md</span>
          </div>
          <div className="sq-validation-id">
            <span className="sq-validation-name">
              {HEADLINE.model.toUpperCase()}
            </span>
            <span className="sq-validation-arch">
              {MODEL.architecture} · {MODEL.parameters.toLocaleString("en-US")}{" "}
              parameters
            </span>
          </div>
          <div className="sq-validation-grid">
            <div className="sq-metric">
              <span className="sq-metric-k">Held-out IoU</span>
              <span className="sq-metric-v">{f3(HEADLINE.pooledIoU)}</span>
              <span className="sq-metric-note">
                pooled · baseline {f3(HEADLINE.baselinePooledIoU)}
              </span>
            </div>
            <div className="sq-metric">
              <span className="sq-metric-k">Held-out F1</span>
              <span className="sq-metric-v">{f3(HEADLINE.pooledF1)}</span>
              <span className="sq-metric-note">
                pooled · baseline {f3(HEADLINE.baselinePooledF1)}
              </span>
            </div>
            <div className="sq-metric">
              <span className="sq-metric-k">Calibration</span>
              <span className="sq-status sq-status--warn">
                <i aria-hidden="true" />
                PARTIAL
              </span>
              <span className="sq-metric-note">
                ECE {CALIBRATION.eceScaled.toFixed(3)} · bar{" "}
                {CALIBRATION.bar.toFixed(3)}
              </span>
            </div>
            <div className="sq-metric">
              <span className="sq-metric-k">Trained on</span>
              <span className="sq-metric-v">{HEADLINE.trainChips}</span>
              <span className="sq-metric-note">
                chips · {TRAINED_REGIONS} regions
              </span>
            </div>
          </div>
        </motion.aside>
      </section>
    </>
  );
}
