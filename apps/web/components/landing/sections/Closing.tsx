"use client";

import Link from "next/link";

import { GlitchText } from "../effects/GlitchText";
import { IconArrow, Reveal } from "../ui";

export function Closing() {
  return (
    <>
      <section className="sq-final" aria-label="Get started">
        <div className="sq-final-glow" aria-hidden="true" />
        <div className="sq-wrap sq-final-inner">
          <Reveal>
            <span className="sq-eyebrow">Ready when you are</span>
          </Reveal>
          <Reveal delay={0.1}>
            <div style={{ width: "min(720px, 88vw)" }}>
              <GlitchText
                as="h2"
                lines={[{ text: "Ask it something.", tone: "gradient" }]}
                minSize={36}
                maxSize={84}
                seed={41}
              />
            </div>
          </Reveal>
          <Reveal delay={0.2}>
            <p className="sq-sub" style={{ margin: 0 }}>
              Run a mission over the Assam floodplain and watch every stage land, with the
              source of every value marked.
            </p>
          </Reveal>
          <Reveal delay={0.3}>
            <div className="sq-cta-row" style={{ justifyContent: "center" }}>
              <Link href="/console" className="sq-btn sq-btn-primary">
                Open the console
                <IconArrow />
              </Link>
              <Link href="/missions" className="sq-btn sq-btn-ghost">
                Browse missions
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="sq-footer">
        <div className="sq-wrap sq-footer-inner">
          <div>
            <div className="sq-brand" style={{ color: "var(--sq-ink)" }}>
              <span className="sq-brand-mark" aria-hidden="true" />
              SATQUERY
            </div>
            <div style={{ marginTop: 10 }}>Smart India Hackathon 2026</div>
          </div>
          <nav className="sq-footer-links" aria-label="App">
            <Link href="/console">Console</Link>
            <Link href="/missions">Missions</Link>
            <Link href="/monitoring">Monitoring</Link>
            <Link href="/admin">Admin</Link>
          </nav>
          <div className="sq-mono" style={{ maxWidth: 360 }}>
            Every figure on this page is copied from reports/evaluation.md and
            reports/calibration.md, which are generated, never hand-written.
          </div>
        </div>
      </footer>
    </>
  );
}
