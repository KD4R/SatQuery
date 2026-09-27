"use client";

/**
 * The opening beat, on every load: the SatQuery mark alone in the middle of the
 * screen -- its cube turning in 3D and settling face-on -- then, after two
 * seconds, it flies to its place in the nav's top-left corner and the planet
 * comes up behind it.
 *
 * The flight is a FLIP: measure the big mark and the nav brand, then transform the
 * big one onto the small one (translate + uniform scale -- the big mark is drawn
 * at exactly 3x the nav brand, so scaling lands it pixel for pixel). When it
 * lands, the overlay is removed and the real nav brand is shown in the same spot.
 *
 * Phases are published on the landing root as data-intro="logo" | "fly" | "done",
 * and space.css keys everything else off that: the nav brand and links wait, the
 * page does not scroll, the globe fades up once the mark has landed.
 *
 * The very first time a browser opens the site, a two-second opening sound plays
 * with it (see introSound.ts); never again after that.
 *
 * Skipped under reduced motion: a small inline script, run while the HTML is still
 * being parsed, hides the overlay before first paint so there is no flash. With
 * JavaScript off, a <noscript> style does the same. A click or any key skips
 * straight to the flight.
 */

import { useEffect, useRef } from "react";

import { playIntroSoundOnce } from "./introSound";

export type IntroPhase = "logo" | "fly" | "done";

const HOLD_MS = 2000;
const FLY_MS = 850;

/* Runs during HTML parsing, before first paint. Inserts a style rather than
   touching <html> or <body> attributes, so React's hydration sees nothing changed. */
const SKIP_SCRIPT = `try{if(matchMedia("(prefers-reduced-motion: reduce)").matches){var s=document.createElement("style");s.id="sq-intro-skip";s.textContent=".sq-boot{display:none!important}.sq-landing[data-intro] .sq-intro-wait,.sq-landing[data-intro] .sq-intro-brand{opacity:1!important;transform:none!important;transition:none!important}.sq-landing[data-intro]{overflow-y:auto!important}";document.head.appendChild(s)}}catch(e){}`;

const NOSCRIPT_STYLE =
  ".sq-boot{display:none!important}.sq-landing[data-intro] .sq-intro-wait,.sq-landing[data-intro] .sq-intro-brand{opacity:1!important;transform:none!important}.sq-landing[data-intro]{overflow-y:auto!important}";

export function BrandIntro({
  phase,
  onPhase,
}: {
  phase: IntroPhase;
  onPhase: (p: IntroPhase) => void;
}) {
  const markRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      onPhase("done");
      return;
    }
    const stopSound = playIntroSoundOnce();

    let landed: ReturnType<typeof setTimeout>;
    let flown = false;
    const fly = () => {
      if (flown) return;
      flown = true;
      const mark = markRef.current;
      const target = document.querySelector<HTMLElement>(".sq-nav .sq-brand");
      if (mark && target) {
        const a = mark.getBoundingClientRect();
        const b = target.getBoundingClientRect();
        const s = b.width / a.width;
        mark.style.transform = `translate(${b.left - a.left}px, ${b.top - a.top}px) scale(${s})`;
      }
      onPhase("fly");
      landed = setTimeout(() => {
        onPhase("done");
        // give a sound that started late (on a click) time to finish
        setTimeout(stopSound, 2200);
      }, FLY_MS);
    };

    const hold = setTimeout(fly, HOLD_MS);
    const skip = () => fly();
    window.addEventListener("keydown", skip, { once: true });
    window.addEventListener("pointerdown", skip, { once: true });
    return () => {
      clearTimeout(hold);
      clearTimeout(landed);
      window.removeEventListener("keydown", skip);
      window.removeEventListener("pointerdown", skip);
      stopSound();
    };
  }, [onPhase]);

  if (phase === "done") return null;

  return (
    <div className="sq-boot" data-phase={phase} aria-hidden="true">
      <script dangerouslySetInnerHTML={{ __html: SKIP_SCRIPT }} />
      <noscript>
        <style>{NOSCRIPT_STYLE}</style>
      </noscript>
      <span ref={markRef} className="sq-boot-brand">
        <span className="sq-boot-mark">
          <span className="sq-cube">
            {["front", "back", "right", "left", "top", "bottom"].map((f) => (
              <i key={f} className={`sq-cube-face sq-cube-${f}`} />
            ))}
          </span>
        </span>
        <span className="sq-boot-word">SatQuery</span>
      </span>
    </div>
  );
}
