"use client";

import Link from "next/link";

import { IconArrow, Reveal } from "../ui";
import { SectionIndex } from "./SectionIndex";

export function Closing() {
  return (
    <>
      <section className="sq-final" aria-label="Get started">
        <div className="sq-wrap sq-final-inner">
          <Reveal className="sq-final-title">
            <SectionIndex n={6} label="Ready when you are" />
            <h2 className="sq-h2">
              Ask it something.
              <br />
              <span className="is-quiet">Check every answer.</span>
            </h2>
          </Reveal>
          <Reveal delay={0.1} className="sq-final-action">
            <p className="sq-sub">
              Run a mission over the Assam floodplain and watch every stage land, with the
              source of every value marked.
            </p>
            <div className="sq-cta-row">
              <Link href="/console" className="sq-btn sq-btn--primary">
                Open the console
                <IconArrow />
              </Link>
              <Link href="/missions" className="sq-btn sq-btn--secondary">
                <span className="sq-btn-rule">Browse missions</span>
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="sq-footer">
        <div className="sq-wrap sq-footer-inner">
          <div>
            <div className="sq-brand">
              <span className="sq-brand-mark" aria-hidden="true" />
              SatQuery
            </div>
            <div className="sq-footer-meta">Smart India Hackathon 2026</div>
          </div>
          <nav className="sq-footer-links" aria-label="App">
            <Link href="/console">Console</Link>
            <Link href="/missions">Missions</Link>
            <Link href="/monitoring">Monitoring</Link>
            <Link href="/admin">Admin</Link>
          </nav>
          <div className="sq-footer-source">
            Every figure on this page is copied from reports/evaluation.md and
            reports/calibration.md, which are generated, never hand-written.
          </div>
        </div>
      </footer>
    </>
  );
}
