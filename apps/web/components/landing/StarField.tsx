'use client';

import { useEffect, useRef } from 'react';

/**
 * Animated star field canvas — thousands of parallax-scrolling stars
 * that give depth to the dark landing page background.
 */
export function StarField() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const STAR_COUNT = 280;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Deterministic seeded RNG — no randomness, identical on every render
    const rng = (seed: number) => {
      const x = Math.sin(seed) * 10000;
      return x - Math.floor(x);
    };

    const stars = Array.from({ length: STAR_COUNT }, (_, i) => ({
      x: rng(i * 3.14159 + 1),
      y: rng(i * 2.71828 + 2),
      r: 0.3 + rng(i * 1.41421 + 3) * 1.4,
      speed: 0.01 + rng(i * 1.73205 + 4) * 0.03,
      opacity: 0.15 + rng(i * 2.23606 + 5) * 0.85,
      twinkle: rng(i * 2.64575 + 6) * Math.PI * 2,
    }));

    let raf = 0;
    let stopped = false;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.floor(canvas.clientWidth * dpr);
      canvas.height = Math.floor(canvas.clientHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      for (const s of stars) {
        const twinkle = reduce ? 1 : 0.5 + 0.5 * Math.sin(t * s.speed * 6 + s.twinkle);
        const alpha = s.opacity * twinkle;
        ctx.beginPath();
        ctx.arc(s.x * w, s.y * h, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.fill();
      }

      if (!stopped && !reduce) {
        raf = requestAnimationFrame(() => draw(performance.now() / 1000));
      }
    };

    resize();
    draw(0);

    const onResize = () => {
      resize();
      draw(reduce ? 0 : performance.now() / 1000);
    };
    window.addEventListener('resize', onResize);

    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      style={{ width: '100%', height: '100%', display: 'block' }}
    />
  );
}
