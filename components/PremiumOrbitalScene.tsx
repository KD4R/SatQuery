'use client';

import { useEffect, useState } from 'react';
import styles from './PremiumOrbitalScene.module.css';

/**
 * GPU-safe premium orbital hero.
 * Pure SVG/CSS: no WebGL renderer, no Three.js context to lose.
 */
export default function PremiumOrbitalScene() {
  const [engaged, setEngaged] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReduceMotion(query.matches);
    sync();
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

  return (
    <div
      className={`${styles.scene} ${engaged ? styles.engaged : ''} ${reduceMotion ? styles.reduceMotion : ''}`}
      onPointerEnter={() => setEngaged(true)}
      onPointerLeave={() => setEngaged(false)}
      aria-label="Interactive orbital mission model"
    >
      <div className={styles.stars} aria-hidden="true" />
      <div className={styles.gridPlane} aria-hidden="true" />
      <div className={`${styles.ring} ${styles.ringOne}`} aria-hidden="true" />
      <div className={`${styles.ring} ${styles.ringTwo}`} aria-hidden="true" />
      <div className={`${styles.ring} ${styles.ringThree}`} aria-hidden="true" />

      <div className={styles.earth} aria-hidden="true">
        <svg className={styles.earthSvg} viewBox="0 0 420 420" role="presentation">
          <defs>
            <radialGradient id="earthSurface" cx="31%" cy="25%" r="78%">
              <stop offset="0" stopColor="#607a58" />
              <stop offset="0.34" stopColor="#263b2b" />
              <stop offset="0.72" stopColor="#101c13" />
              <stop offset="1" stopColor="#070d09" />
            </radialGradient>
            <linearGradient id="landFill" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#a5bd91" stopOpacity=".86" />
              <stop offset="1" stopColor="#4d6949" stopOpacity=".5" />
            </linearGradient>
            <radialGradient id="atmo" cx="50%" cy="50%" r="50%">
              <stop offset="78%" stopColor="transparent" />
              <stop offset="95%" stopColor="#b8e47b" stopOpacity=".08" />
              <stop offset="100%" stopColor="#b8e47b" stopOpacity=".5" />
            </radialGradient>
            <clipPath id="earthClip"><circle cx="210" cy="210" r="204" /></clipPath>
          </defs>

          <circle className="earth-surface" cx="210" cy="210" r="204" fill="url(#earthSurface)" />
          <g clipPath="url(#earthClip)" className={styles.longitudes}>
            <ellipse cx="210" cy="210" rx="72" ry="204" />
            <ellipse cx="210" cy="210" rx="145" ry="204" />
            <ellipse cx="210" cy="210" rx="204" ry="204" />
            <ellipse cx="210" cy="210" rx="204" ry="72" />
            <ellipse cx="210" cy="210" rx="204" ry="145" />
            <path d="M10 118 Q210 178 410 118 M10 302 Q210 242 410 302" />
          </g>
          <g clipPath="url(#earthClip)" className={styles.land}>
            <path d="M86 91l26-18 22 7 8 18-13 16 7 19-20 18-11 34-21-11-3-25-15-14 8-20z" />
            <path d="M150 185l27 8 16 21-8 19 13 20-13 28-18 15-11-30-17-20 4-24-9-16z" />
            <path d="M232 104l31-14 31 9 16 22-11 17-26 3-12 18-25-5-15-20z" />
            <path d="M286 166l27-5 28 17-8 17 17 17-17 17-28-5-14 18-18-21 8-24-11-17z" />
            <path d="M237 263l25 6 15 24-12 22-25 14-13-20 8-20-11-15z" />
            <path d="M331 255l25 5 14 17-13 18-24-2-13-17z" />
          </g>
          <circle className={styles.atmosphere} cx="210" cy="210" r="207" fill="url(#atmo)" />
          <circle className={styles.edge} cx="210" cy="210" r="204" />
          <path className={styles.scan} d="M16 118 Q210 75 404 118" />
        </svg>
      </div>

      <button
        type="button"
        className={styles.satellite}
        aria-label="Toggle satellite orbit mode"
        onClick={(event) => {
          event.stopPropagation();
          setEngaged((value) => !value);
        }}
      >
        <span className={styles.satBody} />
        <span className={`${styles.satPanel} ${styles.satPanelLeft}`} />
        <span className={`${styles.satPanel} ${styles.satPanelRight}`} />
        <span className={styles.satMast} />
        <span className={styles.satSignal} />
      </button>

      <div className={styles.crosshair} aria-hidden="true"><i /><i /><i /><i /></div>

      <div className={styles.coordinate} aria-hidden="true">16.30° N&nbsp;&nbsp;80.44° E</div>
      <div className={styles.liveDot} aria-hidden="true" />
    </div>
  );
}
