"use client";

/**
 * Evidence first: the three behaviours that make the console trustworthy, each shown
 * with a miniature of what the console actually renders.
 */

import { CALIBRATION } from "../facts";
import { Reveal, useSpotlight } from "../ui";

function Card({ children, delay }: { children: React.ReactNode; delay: number }) {
  const ref = useSpotlight<HTMLDivElement>();
  return (
    <Reveal delay={delay}>
      <div ref={ref} className="sq-card sq-principle sq-proof-card">
        {children}
      </div>
    </Reveal>
  );
}

const pos = (v: number) => `${(v / 0.1) * 100}%`; // ECE axis, 0 .. 0.10

export function Principles() {
  return (
    <section id="honesty" className="sq-section">
      <div className="sq-wrap">
        <Reveal className="sq-section-head">
          <span className="sq-eyebrow">Evidence first</span>
          <h2 className="sq-h2">
            It tells you what it <span className="sq-grad-text">doesn&rsquo;t know.</span>
          </h2>
          <p className="sq-sub">
            A flood map that fills its gaps with confident guesses is worse than no map. These
            are the rules the console is built around.
          </p>
        </Reveal>

        <div className="sq-principles">
          <Card delay={0}>
            <div className="sq-mini">
              <div className="sq-mini-row">
                <span>Acquired</span>
                <span className="sq-mini-na">NOT AVAILABLE</span>
              </div>
              <div className="sq-mini-row">
                <span>Area analysed</span>
                <span style={{ color: "var(--sq-ink)" }}>inside swath only</span>
              </div>
            </div>
            <h3>&ldquo;Not available&rdquo; beats a guess.</h3>
            <p>
              When a value is unknown the console says so, and says why. Nothing is back-filled
              with something plausible.
            </p>
          </Card>

          <Card delay={0.08}>
            <div className="sq-mini">
              <div className="sq-mini-row">
                <span>Expected calibration error</span>
              </div>
              <div
                className="sq-ece"
                role="img"
                aria-label={`Raw ${CALIBRATION.eceRaw}, temperature-scaled ${CALIBRATION.eceScaled}, bar ${CALIBRATION.bar}. Lower is better; scaled still misses the bar.`}
              >
                {(
                  [
                    ["raw", CALIBRATION.eceRaw, "#6e77a8"],
                    ["scaled", CALIBRATION.eceScaled, "var(--sq-amber)"],
                  ] as const
                ).map(([label, v, c]) => (
                  <div key={label} className="sq-ece-row">
                    <span>{label}</span>
                    <span className="sq-ece-track">
                      <span className="sq-ece-fill" style={{ width: pos(v), background: c }} />
                      <span className="sq-ece-bar" style={{ left: pos(CALIBRATION.bar) }} />
                    </span>
                    <span style={{ color: c, textAlign: "right" }}>{v.toFixed(4)}</span>
                  </div>
                ))}
                <div className="sq-ece-axis">
                  <span />
                  <span>
                    <em style={{ left: pos(CALIBRATION.bar) }}>bar {CALIBRATION.bar.toFixed(2)} · lower is better</em>
                  </span>
                  <span />
                </div>
              </div>
            </div>
            <h3>Confidence is shown against its bar.</h3>
            <p>
              Temperature scaling more than halved the error, but it still misses the bar set
              before the test — so the model&rsquo;s scores are never presented as probabilities.
            </p>
          </Card>

          <Card delay={0.16}>
            <div className="sq-mini">
              <div className="sq-badges">
                <span className="sq-badge">FIXTURE</span>
                <span className="sq-badge">ENV: DEMO</span>
              </div>
              <div className="sq-mini-row" style={{ marginTop: 8 }}>
                <span>Gateway</span>
                <span style={{ color: "var(--sq-ink)" }}>unreachable — shown as such</span>
              </div>
            </div>
            <h3>Demo data is badged. Always.</h3>
            <p>
              Every surface fed by demo data wears a badge, and a failed live call shows the
              failure — it never quietly falls back to a fixture.
            </p>
          </Card>
        </div>
      </div>
    </section>
  );
}
