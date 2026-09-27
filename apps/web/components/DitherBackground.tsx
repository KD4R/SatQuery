"use client";

/**
 * The dashboard family's animated background: React Bits' Dither, fixed
 * full-bleed behind the working UI on every dashboard page.
 *
 * The wave is tuned to the landing palette (components/landing/space.css):
 * slate dither waves on the near-black ground — structure, not decoration.
 * `disableAnimation` carries prefers-reduced-motion, so the field renders
 * as a still frame for people who opt out; the canvas itself stays (it is
 * the page's ground colour).
 *
 * three.js is heavy, so the actual component is dynamically imported and
 * only mounts when motion is allowed.
 */

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const Dither = dynamic(() => import("./backgrounds/Dither"), {
  ssr: false,
  loading: () => null,
});

export default function DitherBackground() {
  const [reducedMotion, setReducedMotion] = useState(true);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReducedMotion(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  return (
    <div className="dither-bg" aria-hidden="true">
      <Dither
        // Slate ink on the near-black ground — the landing's structure hue.
        waveColor={[0.42, 0.44, 0.47]}
        backgroundColor={[0.031, 0.031, 0.031]}
        colorNum={4}
        waveAmplitude={0.3}
        waveFrequency={3}
        waveSpeed={0.05}
        disableAnimation={reducedMotion}
        enableMouseInteraction={true}
        mouseRadius={0.3}
      />
    </div>
  );
}
