"use client";

/**
 * Why radar. Full-bleed landscape interlude.
 *
 * The three facts are physics, not product claims: synthetic aperture radar brings
 * its own illumination (so night does not matter), microwaves at C-band pass
 * through cloud, and calm water reflects the pulse away from the satellite
 * (specular reflection), so it appears dark. The landscape behind the copy acts
 * that last one out -- watch the radar sweep light the hills and skip the water.
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
    <section id="radar" className="sq-radar" aria-label="Why radar">
      <Landscape className="sq-radar-canvas" />
      <div className="sq-wrap sq-radar-copy">
        <Reveal>
          <SectionIndex n={3} label="Why radar" />
        </Reveal>
        <Reveal delay={0.08}>
          <h2 className="sq-h2">
            Floods come with cloud.
            <br />
            <span className="is-quiet">Radar doesn&rsquo;t care.</span>
          </h2>
        </Reveal>
        <Reveal delay={0.16}>
          <p className="sq-sub">
            Sentinel-1 carries a synthetic aperture radar. Watch the pulse sweep the ground
            below: the hills light up, the water in the valleys stays black. Dark means water.
          </p>
        </Reveal>

        <Reveal delay={0.1} className="sq-radar-facts">
          {FACTS.map((f) => (
            <div key={f.title} className="sq-radar-fact">
              <span className="sq-icon">{f.icon}</span>
              <h4>{f.title}</h4>
              <p>{f.body}</p>
            </div>
          ))}
        </Reveal>
      </div>
    </section>
  );
}
