"use client";

/**
 * Hero.
 *
 * Left: what it is, in one headline and one sentence, then something to try and a
 * way in. Right: the planet, with the model's story on it, and the model card --
 * the handful of facts a judge would ask for first, each traceable to a report.
 *
 * The previous hero had two problems the redesign is for. The left column was a
 * small typed line under the headline, easy to miss. The right column was a long
 * list of animated "system checks" whose percentages were theatre -- only one of
 * them meant anything, and "Confidence calibration 58%" read as a score when it was
 * an ECE of 0.058. The model card states the same shortfall plainly instead.
 */

import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";

import { GlitchText } from "../effects/GlitchText";
import { CALIBRATION, HEADLINE, MODEL, REGIONS, f3, ratio } from "../facts";
import { SpaceGlobe } from "../SpaceGlobe";
import { IconArrow } from "../ui";

const EXAMPLES = [
  "Map new flood water along the Brahmaputra near Nagaon.",
  "Where has water spread in Assam since the last radar pass?",
  "Show the flooded area — and tell me what you couldn't see.",
];

function useTypewriter(lines: string[]) {
  const reduce = useReducedMotion();
  const [state, setState] = useState({ line: 0, chars: lines[0]!.length });

  useEffect(() => {
    if (reduce) return;
    let line = 0;
    let chars = 0;
    let deleting = false;
    let timer: ReturnType<typeof setTimeout>;
    setState({ line: 0, chars: 0 });
    const tick = () => {
      const full = lines[line]!;
      if (!deleting) {
        chars += 1;
        setState({ line, chars });
        if (chars >= full.length) {
          deleting = true;
          timer = setTimeout(tick, 2600);
          return;
        }
        timer = setTimeout(tick, 34 + (full.charCodeAt(chars - 1) % 5) * 9);
      } else {
        chars -= 2;
        if (chars <= 0) {
          chars = 0;
          deleting = false;
          line = (line + 1) % lines.length;
        }
        setState({ line, chars });
        timer = setTimeout(tick, chars === 0 ? 420 : 16);
      }
    };
    timer = setTimeout(tick, 900);
    return () => clearTimeout(timer);
  }, [lines, reduce]);

  return lines[state.line]!.slice(0, state.chars);
}

const ease = [0.16, 1, 0.3, 1] as const;

function Rise({ children, delay }: { children: React.ReactNode; delay: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: reduce ? 0 : delay, duration: 0.8, ease }}
    >
      {children}
    </motion.div>
  );
}

const TRAINED_REGIONS = REGIONS.filter((r) => r.split === "trained").length;

export function Hero() {
  const typed = useTypewriter(EXAMPLES);
  const reduce = useReducedMotion();

  return (
    <section className="sq-wrap sq-hero" aria-label="Introduction">
      <div className="sq-hero-copy">
        <Rise delay={0.05}>
          <span className="sq-chip">
            <span className="sq-dot is-ice" />
            Smart India Hackathon 2026 · SAR flood intelligence
          </span>
        </Rise>

        <Rise delay={0.15}>
          <GlitchText
            as="h1"
            lines={[
              { text: "Ask a question." },
              { text: "Get an answer" },
              { text: "with its evidence.", tone: "gradient" },
            ]}
            minSize={34}
            maxSize={76}
          />
        </Rise>

        <Rise delay={0.3}>
          <p className="sq-lede">
            SatQuery maps flood water from <b>Sentinel-1 radar</b>, which sees through the
            cloud that floods arrive with — and hands back the evidence, the caveats, and
            what it could not measure.
          </p>
        </Rise>

        <Rise delay={0.42}>
          <div className="sq-query" aria-label="Example questions">
            <div className="sq-query-bar">
              <i />
              <i />
              <i />
              <span style={{ marginLeft: 8 }}>ASK IN PLAIN LANGUAGE</span>
            </div>
            <div className="sq-query-body">
              <span className="sq-prompt" aria-hidden="true">
                ›
              </span>
              <span>{typed}</span>
              <span className="sq-caret" aria-hidden="true" />
            </div>
          </div>
        </Rise>

        <Rise delay={0.54}>
          <div className="sq-cta-row">
            <Link href="/console" className="sq-btn sq-btn-primary">
              Enter mission console
              <IconArrow />
            </Link>
            <a href="#how" className="sq-btn sq-btn-ghost">
              See how it works
            </a>
          </div>
        </Rise>

        <Rise delay={0.66}>
          <div className="sq-trust">
            <span>
              <b>{ratio(HEADLINE.pooledIoU, HEADLINE.baselinePooledIoU)}</b> the classical baseline
            </span>
            <span>
              <b>{HEADLINE.heldOutChips}</b> unseen test chips
            </span>
            <span>
              <b>{HEADLINE.regionCount}</b> flood regions
            </span>
          </div>
        </Rise>
      </div>

      <div className="sq-hero-visual">
        <SpaceGlobe />

        <span className="sq-globe-hint" aria-hidden="true">
          drag to spin · hover a region
        </span>

        {/* Model card as a strip under the planet. It overlaps only the south polar
            limb, which auto-rotation never brings anything interesting into -- a card
            beside the globe ends up covering India, where every arc lands. */}
        <motion.aside
          className="sq-card sq-model"
          aria-label="Model card"
          initial={reduce ? false : { opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: reduce ? 0 : 0.9, duration: 0.9, ease }}
        >
          <div className="sq-model-head">
            <span>
              <b className="sq-model-name">{HEADLINE.model}</b>
              <span className="sq-model-sub">
                {MODEL.architecture} · {MODEL.parameters.toLocaleString("en-US")} parameters
              </span>
            </span>
            <span className="sq-legend">
              <span>
                <i className="sq-dot is-ice" /> trained on
              </span>
              <span>
                <i className="sq-dot is-violet" /> held out
              </span>
              <span>
                <i className="sq-dot is-beacon" /> demo area
              </span>
            </span>
          </div>

          <div className="sq-model-grid">
            <div className="sq-model-cell">
              <span className="sq-model-k">Held-out IoU</span>
              <span className="sq-model-v">{f3(HEADLINE.pooledIoU)}</span>
              <span className="sq-model-note">pooled · baseline {f3(HEADLINE.baselinePooledIoU)}</span>
            </div>
            <div className="sq-model-cell">
              <span className="sq-model-k">Held-out F1</span>
              <span className="sq-model-v">{f3(HEADLINE.pooledF1)}</span>
              <span className="sq-model-note">pooled · baseline {f3(HEADLINE.baselinePooledF1)}</span>
            </div>
            <div className="sq-model-cell">
              <span className="sq-model-k">Calibration</span>
              <span className="sq-status is-amber">PARTIAL</span>
              <span className="sq-model-note">
                ECE {CALIBRATION.eceScaled.toFixed(3)} · bar {CALIBRATION.bar.toFixed(3)}
              </span>
            </div>
            <div className="sq-model-cell">
              <span className="sq-model-k">Trained on</span>
              <span className="sq-model-v">{HEADLINE.trainChips}</span>
              <span className="sq-model-note">
                chips · {TRAINED_REGIONS} regions
              </span>
            </div>
          </div>
        </motion.aside>
      </div>

      <div className="sq-scroll-cue" aria-hidden="true">
        SCROLL
        <i />
      </div>
    </section>
  );
}
