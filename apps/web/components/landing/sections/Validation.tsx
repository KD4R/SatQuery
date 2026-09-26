"use client";

/**
 * Validation: the evaluation tables, drawn.
 *
 * Both charts are copied row-for-row from reports/evaluation.md, including the parts
 * that do not flatter the model: it is weakest on nearly-dry chips, it trails the
 * baseline slightly on the wettest ones, and Mekong and Nigeria come out a hair
 * below the baseline even though the model trained there. A validation section that
 * only showed wins would be the least credible thing on the page.
 */

import { motion, useReducedMotion } from "framer-motion";

import { GENERALISATION, REGIONS, STRATA, f3 } from "../facts";
import { Reveal } from "../ui";
import { SectionIndex } from "./SectionIndex";

const ORDER = [...REGIONS].sort((a, b) => {
  if (a.split !== b.split) return a.split === "held-out" ? -1 : 1;
  return b.modelIoU - a.modelIoU;
});
const MAX = 0.6; // bar scale; the largest region IoU is 0.513

export function Validation() {
  const reduce = useReducedMotion();
  const grow = (pct: number, delay: number) =>
    reduce
      ? { style: { width: `${pct}%` } }
      : {
          initial: { width: 0 },
          whileInView: { width: `${pct}%` },
          viewport: { once: true, margin: "-40px" },
          transition: { delay, duration: 1, ease: [0.16, 1, 0.3, 1] as const },
        };

  return (
    <section id="validation" className="sq-section">
      <div className="sq-wrap">
        <Reveal className="sq-section-head">
          <SectionIndex n={4} label="Validation" />
          <h2 className="sq-h2">
            Tested where it had <span className="is-quiet">never been.</span>
          </h2>
          <p className="sq-sub">
            India and Somalia were held out of training entirely. Only those two
            rows measure generalisation — the rest are shown so you can see the
            gap.
          </p>
        </Reveal>

        <div className="sq-val">
          <Reveal>
            <div className="sq-panel sq-val-card">
              <div className="sq-val-title">
                IoU by region
                <span className="sq-val-legend">
                  <span>
                    <i className="sq-swatch sq-swatch--b" /> held out
                  </span>
                  <span>
                    <i className="sq-swatch sq-swatch--a" /> trained
                  </span>
                  <span>
                    <i className="sq-swatch sq-swatch--slate" /> baseline
                  </span>
                </span>
              </div>
              <div
                className="sq-bars"
                role="table"
                aria-label="IoU by region, model and baseline"
              >
                {ORDER.map((r, i) => (
                  <div
                    key={r.name}
                    role="row"
                    className={`sq-bar-row${r.split === "held-out" ? " is-held" : ""}`}
                  >
                    <span className="sq-bar-name" role="rowheader">
                      {r.name}
                    </span>
                    <span
                      className="sq-bar-track"
                      role="cell"
                      aria-label={`model ${f3(r.modelIoU)}, baseline ${f3(r.baselineIoU)}`}
                    >
                      <motion.span
                        className="sq-bar-model"
                        {...grow((r.modelIoU / MAX) * 100, i * 0.05)}
                      />
                      <motion.span
                        className="sq-bar-base"
                        {...grow((r.baselineIoU / MAX) * 100, 0.1 + i * 0.05)}
                      />
                    </span>
                    <span className="sq-bar-val" role="cell">
                      {f3(r.modelIoU)}
                    </span>
                  </div>
                ))}
              </div>
              <div className="sq-val-foot">
                Mean per-chip IoU is {f3(GENERALISATION.trainedMeanIoU)} on
                trained regions and {f3(GENERALISATION.heldOutMeanIoU)} held out
                — a gap of +{f3(GENERALISATION.gap)}. A large gap means
                memorisation; near zero, that it generalises as well as it fits.
              </div>
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="sq-panel sq-val-card">
              <div className="sq-val-title">
                By how much water the chip holds
                <span className="sq-val-legend">
                  <span>
                    <i className="sq-swatch sq-swatch--a" /> model
                  </span>
                  <span>
                    <i className="sq-swatch sq-swatch--slate" /> baseline
                  </span>
                </span>
              </div>
              <div className="sq-strata">
                {STRATA.map((s, i) => (
                  <div
                    key={s.label}
                    className="sq-stratum-bars"
                    aria-label={`${s.label}: model ${f3(s.modelIoU)}, baseline ${f3(s.baselineIoU)}`}
                  >
                    <motion.div
                      className="sq-stratum-model"
                      {...(reduce
                        ? { style: { height: `${s.modelIoU * 100}%` } }
                        : {
                            initial: { height: 0 },
                            whileInView: { height: `${s.modelIoU * 100}%` },
                            viewport: { once: true },
                            transition: {
                              delay: i * 0.08,
                              duration: 1,
                              ease: [0.16, 1, 0.3, 1] as const,
                            },
                          })}
                    >
                      <span>{f3(s.modelIoU)}</span>
                    </motion.div>
                    <motion.div
                      className="sq-stratum-base"
                      {...(reduce
                        ? { style: { height: `${s.baselineIoU * 100}%` } }
                        : {
                            initial: { height: 0 },
                            whileInView: { height: `${s.baselineIoU * 100}%` },
                            viewport: { once: true },
                            transition: {
                              delay: 0.1 + i * 0.08,
                              duration: 1,
                              ease: [0.16, 1, 0.3, 1] as const,
                            },
                          })}
                    />
                  </div>
                ))}
              </div>
              <div className="sq-strata-labels" aria-hidden="true">
                {STRATA.map((s) => (
                  <div key={s.label}>
                    {s.label}
                    <small>{s.chips} chips</small>
                  </div>
                ))}
              </div>
              <div className="sq-val-foot">
                Strongest where floods are large. Weakest when a chip is almost
                dry, and slightly behind the baseline on the wettest chips (
                {f3(STRATA[3]!.modelIoU)} vs {f3(STRATA[3]!.baselineIoU)}). A
                single average would hide both.
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
