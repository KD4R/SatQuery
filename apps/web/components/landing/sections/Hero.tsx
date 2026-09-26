"use client";

/**
 * The opening, in three beats.
 *
 *   1. Stage   -- the planet first, full screen, with the ten evaluation regions on
 *                 it and nothing competing: a caption, a legend, a scroll cue.
 *   2. Reveal  -- scrolling turns the headline up word by word in 3D, then the one
 *                 sentence that says how it works.
 *   3. Intro   -- what you would type (the query console), the way in, three
 *                 measured facts, and the model validation card: the numbers a judge
 *                 asks for first, each traceable to reports/evaluation.md or
 *                 reports/calibration.md.
 */

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";

import { CALIBRATION, HEADLINE, MODEL, REGIONS, f3, ratio } from "../facts";
import { HeroHeadline } from "../HeroHeadline";
import { QueryConsole } from "../QueryConsole";
import { SpaceGlobe } from "../SpaceGlobe";
import { IconArrow, Reveal } from "../ui";

const ease = [0.16, 1, 0.3, 1] as const;

const TRAINED_REGIONS = REGIONS.filter((r) => r.split === "trained").length;
const HELD_OUT = REGIONS.filter((r) => r.split === "held-out").map(
  (r) => r.name,
);

export function Hero() {
  const reduce = useReducedMotion();

  return (
    <>
      {/* 1 ── the planet ───────────────────────────────────────────────── */}
      <section className="sq-stage" aria-label="Evaluation regions">
        <figure className="sq-wrap sq-stage-figure sq-intro-wait">
          <span className="sq-label sq-stage-kicker">
            <i aria-hidden="true" />
            Smart India Hackathon 2026 · SAR flood intelligence
          </span>

          <SpaceGlobe className="sq-globe--stage" />

          <figcaption className="sq-stage-caption">
            <span className="sq-figure-legend">
              <span>
                <i className="sq-key sq-key--a" /> trained on
              </span>
              <span>
                <i className="sq-key sq-key--b" /> held out
              </span>
              <span>
                <i className="sq-key sq-key--signal" /> demo area
              </span>
            </span>
            <span className="sq-stage-note">
              Fig. 1 · Sen1Floods11 regions · {HELD_OUT.join(", ")} held out of
              training
            </span>
            <span className="sq-hover-hint" aria-hidden="true">
              <i />
              drag to rotate · hover a region
            </span>
          </figcaption>

          <a href="#intro" className="sq-scroll-cue">
            Scroll
            <i aria-hidden="true" />
          </a>
        </figure>
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
