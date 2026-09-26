"use client";

/**
 * Why radar.
 *
 * Header, then the landscape framed as a viewer -- an illustration of what the
 * radar does, not data -- then the three facts in a row beneath it.
 *
 * The facts are physics, not product claims: synthetic aperture radar brings its
 * own illumination (so night does not matter), microwaves at C-band pass through
 * cloud, and calm water reflects the pulse away from the satellite (specular
 * reflection), so it appears dark. The landscape acts that last one out: the
 * pulse lights the hills orange and skips the water.
 */

import { Landscape } from "../effects/Landscape";
import { IconCloud, IconMoon, IconWaves, Reveal } from "../ui";
import { SectionIndex } from "./SectionIndex";

const FACTS = [
  {
    icon: <IconCloud />,
    title: "Sees through cloud",
    body: "C-band microwaves pass through the cloud and rain that hide a flood from optical satellites.",
  },
  {
    icon: <IconMoon />,
    title: "Day or night",
    body: "Radar brings its own illumination. A 2 a.m. pass is as useful as a noon one.",
  },
  {
    icon: <IconWaves />,
    title: "Water shows up dark",
    body: "Calm water mirrors the pulse away from the satellite; rough ground scatters it back. The model learns that contrast.",
  },
];

export function Radar() {
  return (
    <section id="radar" className="sq-section" aria-label="Why radar">
      <div className="sq-wrap">
        <Reveal className="sq-section-head sq-radar-head">
          <SectionIndex n={2} label="Why radar" />
          <h2 className="sq-h2">
            Floods come with cloud.
            <br />
            <span className="is-quiet">Radar doesn&rsquo;t care.</span>
          </h2>
          <p className="sq-sub">
            Sentinel-1 carries a synthetic aperture radar. Watch the pulse sweep
            the ground: the hills light up, the water in the valleys stays
            black. Dark means water.
          </p>
        </Reveal>

        <Reveal delay={0.1} className="sq-radar-view">
          <div className="sq-radar-view-head">
            <span>Sentinel-1 · C-band SAR</span>
            <span>Illustration</span>
          </div>
          <Landscape className="sq-radar-canvas" />
          <div className="sq-radar-legend">
            <span>
              <i style={{ background: "var(--c-signal)" }} /> pulse scattered
              back by rough ground
            </span>
            <span>
              <i style={{ background: "var(--c-data-b)" }} /> calm water mirrors
              it away, and stays dark
            </span>
          </div>
        </Reveal>

        <div className="sq-radar-facts">
          {FACTS.map((f, i) => (
            <Reveal key={f.title} delay={0.08 * i} className="sq-radar-fact">
              <div className="sq-radar-fact-top">
                <span className="sq-icon">{f.icon}</span>
                <span className="sq-radar-fact-n">0{i + 1}</span>
              </div>
              <h4>{f.title}</h4>
              <p>{f.body}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
