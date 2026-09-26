"use client";

/**
 * Deep-field background: three depths of stars with parallax against scroll, a few
 * that twinkle, and an occasional meteor.
 *
 * Compositor-only. The first version redrew three viewport-sized star layers onto a
 * canvas every frame; profiling showed that single background costing a fifth of
 * the page's CPU in software rendering, on every section, forever. Now each depth
 * is a 512px tile rendered once, repeated as a CSS background on a layer that is
 * only ever moved with transform -- scrolling it is a GPU composite, not a redraw.
 *
 * No continuous twinkle. A dozen always-running CSS animations looked harmless and
 * measured as the single most expensive thing on the page: anything animating
 * beneath a backdrop-filter card forces that blur to be recomputed every frame. The
 * one meteor animates for a second every nine, and is otherwise inert.
 *
 * The tile repeats every 512px, so the layer is translated by scroll modulo 512 and
 * only needs to be a tile or two taller than the viewport. There is deliberately no
 * idle drift: animating three viewport-sized layers forces a composite every frame
 * even when nothing on the page is moving, and nobody can see 3px a second.
 */

import { useEffect, useRef, useState } from "react";

import { mulberry32 } from "./canvas";

const TILE = 512;

const DEPTHS = [
  { seed: 11, count: 70, size: [0.4, 0.9], alpha: [0.25, 0.55], parallax: 0.04 },
  { seed: 12, count: 28, size: [0.8, 1.3], alpha: [0.45, 0.8], parallax: 0.09 },
  { seed: 13, count: 9, size: [1.2, 1.8], alpha: [0.7, 1.0], parallax: 0.16 },
];

function tile(d: (typeof DEPTHS)[number]): string {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const c = document.createElement("canvas");
  c.width = TILE * dpr;
  c.height = TILE * dpr;
  const x = c.getContext("2d");
  if (!x) return "";
  x.scale(dpr, dpr);
  const rand = mulberry32(d.seed);
  for (let i = 0; i < d.count; i++) {
    const s = d.size[0]! + rand() * (d.size[1]! - d.size[0]!);
    const a = d.alpha[0]! + rand() * (d.alpha[1]! - d.alpha[0]!);
    const hue = rand();
    x.fillStyle =
      hue < 0.12 ? `rgba(255,214,170,${a})` : hue < 0.3 ? `rgba(170,200,255,${a})` : `rgba(235,240,255,${a})`;
    x.beginPath();
    // Keep stars off the tile edge so the repeat seam never cuts one in half.
    x.arc(4 + rand() * (TILE - 8), 4 + rand() * (TILE - 8), s, 0, Math.PI * 2);
    x.fill();
  }
  return c.toDataURL("image/png");
}

interface Props {
  /** The landing page's scroll container. */
  containerRef: React.RefObject<HTMLElement | null>;
}

export function Starfield({ containerRef }: Props) {
  const layerRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [tiles, setTiles] = useState<string[]>([]);

  const meteorRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setTiles(DEPTHS.map(tile));
  }, []);

  // One meteor every nine seconds, on a seeded path; the class is removed after
  // the streak so no animation is running between them.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const el = meteorRef.current;
    if (!el) return;
    const rand = mulberry32(9);
    let off: ReturnType<typeof setTimeout>;
    const fire = () => {
      el.style.left = `${(45 + rand() * 45).toFixed(1)}%`;
      el.style.top = `${(6 + rand() * 30).toFixed(1)}%`;
      el.classList.add("is-flying");
      off = setTimeout(() => el.classList.remove("is-flying"), 1200);
    };
    const first = setTimeout(fire, 2500);
    const every = setInterval(fire, 9000);
    return () => {
      clearTimeout(first);
      clearTimeout(off);
      clearInterval(every);
    };
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let raf = 0;
    const apply = () => {
      raf = 0;
      const y = el.scrollTop;
      layerRefs.current.forEach((layer, i) => {
        if (!layer) return;
        const shift = (y * DEPTHS[i]!.parallax) % TILE;
        layer.style.transform = `translate3d(0, ${-shift}px, 0)`;
      });
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(apply);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    apply();
    return () => {
      el.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, [containerRef]);

  return (
    <div className="sq-stars" aria-hidden="true">
      {DEPTHS.map((_, i) => (
        <div
          key={i}
          ref={(el) => {
            layerRefs.current[i] = el;
          }}
          className="sq-star-layer"
        >
          <div
            className="sq-star-drift"
            style={{
              backgroundImage: tiles[i] ? `url(${tiles[i]})` : undefined,
            }}
          />
        </div>
      ))}
      <i ref={meteorRef} className="sq-meteor" />
    </div>
  );
}
