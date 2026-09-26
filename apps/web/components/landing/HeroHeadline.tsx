"use client";

/**
 * The headline, revealed by scrolling.
 *
 * It lives in a tall section with a sticky stage (.sq-reveal in space.css). As the
 * page scrolls through that section, each word turns up out of the page in 3D --
 * rising and rotating from flat to upright, one after another -- then the underline
 * under "evidence" draws, then the sentence under the headline fades in. The motion
 * is tied to scroll position, not time: scroll back and it reverses.
 *
 * Modelled on the React Bits Pro "3D Text Reveal" (scroll-triggered, GSAP), written
 * here without GSAP because that component needs a paid licence. It is a few style
 * writes per animation frame, only while scrolling.
 *
 * Static-first: the server HTML is the finished headline. Script is what hides the
 * words to begin with, so with JavaScript off -- or reduced motion, where the script
 * leaves everything in place -- the headline is simply there.
 *
 * Once fully revealed, a line glitches when the cursor comes near it: a sliced
 * chromatic split in blue and signal orange, scaled by distance, settling back when
 * the cursor leaves. The copies are pseudo-elements with empty alt text, so the
 * heading's text and accessible name are untouched. Not on touch screens.
 */

import { Fragment, useEffect, useRef } from "react";

const LINES: { text: string; words: string[] }[] = [
  { text: "Ask a question.", words: ["Ask", "a", "question."] },
  { text: "Get an answer", words: ["Get", "an", "answer"] },
  { text: "with its evidence.", words: ["with", "its", "evidence."] },
];

/* Scroll choreography, as fractions of the section's sticky travel. */
const WORD_STAGGER = 0.055;
const WORD_SPAN = 0.2;
const WORDS = LINES.reduce((n, l) => n + l.words.length, 0);
const MARK_AT = (WORDS - 1) * WORD_STAGGER + WORD_SPAN; // underline starts when the last word lands
const MARK_SPAN = 0.1;
const LEDE_AT = MARK_AT + 0.04;
const LEDE_SPAN = 0.14;

const RADIUS = 220;
const STEP_MS = 70;

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
const easeOut = (v: number) => 1 - (1 - v) ** 3;

export function HeroHeadline({ lede }: { lede?: React.ReactNode }) {
  const ref = useRef<HTMLHeadingElement | null>(null);
  const ledeRef = useRef<HTMLDivElement | null>(null);
  const revealed = useRef(true);

  /* ── scroll-linked 3D reveal ─────────────────────────────────────────── */
  useEffect(() => {
    const h = ref.current;
    const section = h?.closest<HTMLElement>(".sq-reveal");
    const scroller = h?.closest<HTMLElement>(".sq-landing");
    if (!h || !section || !scroller) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const words = Array.from(h.querySelectorAll<HTMLElement>("[data-word]"));
    const mark = h.querySelector<HTMLElement>(".sq-headline-mark");
    const lede = ledeRef.current;
    let raf = 0;

    const apply = () => {
      raf = 0;
      const rect = section.getBoundingClientRect();
      const top = rect.top - scroller.getBoundingClientRect().top;
      const travel = Math.max(1, section.offsetHeight - scroller.clientHeight);
      // Start while the section is still sliding up (its top at 45% of the viewport),
      // so the stage is never an empty screen, and finish within the sticky travel.
      const lead = scroller.clientHeight * 0.45;
      const p = clamp01((lead - top) / (travel + lead));

      words.forEach((w, i) => {
        const e = easeOut(clamp01((p - i * WORD_STAGGER) / WORD_SPAN));
        w.style.opacity = e.toFixed(3);
        w.style.transform =
          e >= 1
            ? ""
            : `translate3d(0, ${((1 - e) * 0.55).toFixed(3)}em, 0) rotateX(${((1 - e) * 88).toFixed(1)}deg)`;
      });
      mark?.style.setProperty(
        "--mark",
        easeOut(clamp01((p - MARK_AT) / MARK_SPAN)).toFixed(3),
      );
      if (lede) {
        const e = easeOut(clamp01((p - LEDE_AT) / LEDE_SPAN));
        lede.style.opacity = e.toFixed(3);
        lede.style.transform =
          e >= 1 ? "" : `translate3d(0, ${((1 - e) * 14).toFixed(1)}px, 0)`;
      }
      const done = p >= MARK_AT + MARK_SPAN;
      if (done !== revealed.current) {
        revealed.current = done;
        h.classList.toggle("is-revealed", done);
      }
    };

    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(apply);
    };
    revealed.current = false;
    h.classList.remove("is-revealed");
    apply();
    scroller.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      scroller.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      // leave the finished state behind, never a half-hidden headline
      words.forEach((w) => {
        w.style.opacity = "";
        w.style.transform = "";
      });
      mark?.style.removeProperty("--mark");
      if (lede) {
        lede.style.opacity = "";
        lede.style.transform = "";
      }
      h.classList.add("is-revealed");
    };
  }, []);

  /* ── proximity glitch, once revealed ─────────────────────────────────── */
  useEffect(() => {
    const h = ref.current;
    if (!h) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches)
      return;

    const els = Array.from(h.querySelectorAll<HTMLElement>("[data-glitch]"));
    const cur = new Float32Array(els.length);
    let px = -1e5;
    let py = -1e5;
    let raf = 0;
    let lastStep = 0;

    const slice = (el: HTMLElement) => {
      const a = Math.random() * 70;
      const b = Math.random() * 70;
      el.style.setProperty("--c1", `${a.toFixed(0)}%`);
      el.style.setProperty(
        "--c2",
        `${Math.max(0, 90 - a - 20 * Math.random()).toFixed(0)}%`,
      );
      el.style.setProperty("--c3", `${b.toFixed(0)}%`);
      el.style.setProperty(
        "--c4",
        `${Math.max(0, 90 - b - 20 * Math.random()).toFixed(0)}%`,
      );
      el.style.setProperty("--jx", (Math.random() * 2 - 1).toFixed(2));
    };

    const tick = (now: number) => {
      raf = 0;
      const stepNow = now - lastStep > STEP_MS;
      if (stepNow) lastStep = now;
      const live = revealed.current;
      let busy = false;
      els.forEach((el, i) => {
        const r = el.getBoundingClientRect();
        const dx = Math.max(r.left - px, 0, px - r.right);
        const dy = Math.max(r.top - py, 0, py - r.bottom);
        const target = live
          ? Math.max(0, 1 - Math.hypot(dx, dy) / RADIUS) ** 1.6
          : 0;
        let v = cur[i]! + (target - cur[i]!) * 0.2;
        if (v < 0.004 && target === 0) v = 0;
        cur[i] = v;
        el.style.setProperty("--g", v.toFixed(3));
        if (v > 0 && stepNow) slice(el);
        if (v > 0 || target > 0) busy = true;
      });
      if (busy) raf = requestAnimationFrame(tick);
    };

    const wake = () => {
      if (!raf) raf = requestAnimationFrame(tick);
    };
    const onMove = (e: PointerEvent) => {
      px = e.clientX;
      py = e.clientY;
      wake();
    };
    const onLeave = () => {
      px = -1e5;
      py = -1e5;
      wake();
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, []);

  return (
    <>
      <h1 ref={ref} className="sq-headline is-revealed">
        {LINES.map((line, li) => (
          <span
            key={line.text}
            className={`sq-headline-line${li === 2 ? " sq-headline-line--quiet" : ""}`}
          >
            <span data-glitch={line.text}>
              {line.words.map((w, wi) => (
                <Fragment key={w}>
                  <span data-word="">
                    {w === "evidence." ? (
                      <>
                        <span className="sq-headline-mark">evidence</span>.
                      </>
                    ) : (
                      w
                    )}
                  </span>
                  {wi < line.words.length - 1 ? " " : null}
                </Fragment>
              ))}
            </span>
          </span>
        ))}
      </h1>
      {lede ? (
        <div ref={ledeRef} className="sq-reveal-lede">
          {lede}
        </div>
      ) : null}
    </>
  );
}
