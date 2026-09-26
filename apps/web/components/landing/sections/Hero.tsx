"use client";

/**
 * Hero.
 *
 * Left, in reading order: what it is (headline), how it does it (one sentence),
 * what you would type (the query console), the way in, and three measured facts.
 * Right: a captioned figure -- the planet with the ten evaluation regions on it --
 * and the model validation card, the handful of numbers a judge asks for first,
 * each traceable to reports/evaluation.md or reports/calibration.md.
 */

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";

import { CALIBRATION, HEADLINE, MODEL, REGIONS, f3, ratio } from "../facts";
import { HeroHeadline } from "../HeroHeadline";
import { QueryConsole } from "../QueryConsole";
import { SpaceGlobe } from "../SpaceGlobe";
import { IconArrow } from "../ui";

const ease = [0.16, 1, 0.3, 1] as const;

function Rise({
  children,
  delay,
}: {
  children: React.ReactNode;
  delay: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: reduce ? 0 : delay, duration: 0.7, ease }}
    >
      {children}
    </motion.div>
  );
}

const TRAINED_REGIONS = REGIONS.filter((r) => r.split === "trained").length;
const HELD_OUT = REGIONS.filter((r) => r.split === "held-out").map(
  (r) => r.name,
);

export function Hero() {
  const reduce = useReducedMotion();

  return (
    <section className="sq-wrap sq-hero" aria-label="Introduction">
      <div className="sq-hero-copy">
        <span className="sq-label">
          <i aria-hidden="true" />
          Smart India Hackathon 2026 · SAR flood intelligence
        </span>

        <HeroHeadline />

        <Rise delay={0.55}>
          <p className="sq-lede">
            SatQuery maps flood water from <b>Sentinel-1 radar</b>, which sees
            through the cloud that floods arrive with — and returns the
            evidence, the caveats, and what it could not measure.
          </p>
        </Rise>

        <Rise delay={0.7}>
          <QueryConsole />
        </Rise>

        <Rise delay={0.82}>
          <div className="sq-cta-row">
            <Link href="/console" className="sq-btn sq-btn--primary">
              Enter mission console
              <IconArrow />
            </Link>
            <a href="#how" className="sq-btn sq-btn--secondary">
              <span className="sq-btn-rule">See how it works</span>
            </a>
          </div>
        </Rise>

        <Rise delay={0.94}>
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
        </Rise>
      </div>

      <motion.figure
        className="sq-figure"
        initial={reduce ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: reduce ? 0 : 0.3, duration: 1.2, ease }}
      >
        <figcaption className="sq-figure-caption">
          <div className="sq-figure-head">
            <span className="sq-label">Fig. 1 · Evaluation regions</span>
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
          </div>
          <div className="sq-figure-sub">
            <span>
              Sen1Floods11 · {HELD_OUT.join(", ")} held out of training
            </span>
            <span className="sq-hover-hint" aria-hidden="true">
              <i />
              drag to rotate · hover a region
            </span>
          </div>
        </figcaption>

        <SpaceGlobe />

        <motion.aside
          className="sq-validation"
          aria-label="Model card"
          initial={reduce ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: reduce ? 0 : 1.0, duration: 0.8, ease }}
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
      </motion.figure>
    </section>
  );
}
