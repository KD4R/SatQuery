"use client";

/**
 * The landing page.
 *
 * The first ten seconds have to land on a projector: what this is, that it is
 * spatial and real, and a way in. The next two minutes, for anyone who scrolls,
 * have to answer the questions a sceptical judge asks -- how does it work, why
 * radar, how do you know it works, and what happens when it doesn't know.
 *
 *   Intro         the SatQuery mark alone, then it flies to the nav and the planet rises
 *   Hero          the planet; the headline folding back in 3D as it scrolls; try-it block
 *   Proof         four measured numbers, one of them the accuracy figure we refuse
 *   How it works  the console's own stages, scroll-driven
 *   Why radar     the physics, acted out by the landscape behind it
 *   Validation    the evaluation tables, drawn, including the unflattering rows
 *   Evidence      the three rules the console is built on
 *   Close         a way in, and where every figure came from
 *
 * The page is its own scroll container because app/mission.css locks body scroll
 * for the console, which owns the viewport. Scoping the scroll here keeps that
 * rule intact for every other route.
 *
 * Every figure comes from ./facts, which cites the report table it was copied from.
 */

import { useEffect, useRef, useState } from "react";

import "@fontsource-variable/archivo/wdth.css";
import "@fontsource/sora/latin-500.css";
import "@fontsource/sora/latin-600.css";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "@fontsource/ibm-plex-mono/latin-600.css";
import "./space.css";
import { BrandIntro, type IntroPhase } from "./BrandIntro";
import { Closing } from "./sections/Closing";
import { Hero } from "./sections/Hero";
import { HowItWorks } from "./sections/HowItWorks";
import { Nav } from "./sections/Nav";
import { Principles } from "./sections/Principles";
import { Proof } from "./sections/Proof";
import { Radar } from "./sections/Radar";
import { Validation } from "./sections/Validation";

export default function LandingPage() {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [scrolled, setScrolled] = useState(false);
  const [phase, setPhase] = useState<IntroPhase>("logo");

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const onScroll = () => {
      setScrolled(el.scrollTop > 12);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div ref={rootRef} className="sq-landing" id="top" data-intro={phase}>
      <BrandIntro phase={phase} onPhase={setPhase} />
      <div className="sq-atmos" aria-hidden="true" />

      <div className="sq-content">
        <Nav scrolled={scrolled} />
        <main id="mission-main">
          <Hero phase={phase} />
          <Proof />
          <HowItWorks />
          <Radar />
          <Validation />
          <Principles />
          <Closing />
        </main>
      </div>
    </div>
  );
}
