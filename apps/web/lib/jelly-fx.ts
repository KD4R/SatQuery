/**
 * Pure physics for JellyRadio (and any other squishy chip row).
 *
 * Kept free of React so the numbers can be unit-tested directly: the component
 * maps these outputs onto CSS custom properties and transitions, but every
 * constant that shapes the feel lives here.
 *
 *   swell     how much the active chip grows beyond its resting width (0–1)
 *   barge     extra width the active chip barges into, in px (grown via swell)
 *   shrink    how far a chip that just lost selection dips below rest scale
 *   jelly     global amplitude of the 3D wobble (0 disables it)
 *   bounce    how long the wobble rings out (higher = longer decay)
 *   stagger   ms between neighbouring chips joining the wobble wave
 *   stiffness spring frequency of the wobble, rad/s (higher = faster shake)
 */

export interface JellyParams {
  swell: number;
  barge: number;
  shrink: number;
  jelly: number;
  bounce: number;
  stagger: number;
  stiffness: number;
}

/** The documented defaults — `JellyRadio`'s props fall back to these. */
export const JELLY_DEFAULTS: JellyParams = {
  swell: 0.2,
  barge: 6,
  shrink: 0.05,
  jelly: 1,
  bounce: 0.25,
  stagger: 22,
  stiffness: 580,
};

export type JellyParamsInput = Partial<JellyParams>;

/** Fill an incomplete param object with the documented defaults. */
export function withJellyDefaults(input: JellyParamsInput = {}): JellyParams {
  return { ...JELLY_DEFAULTS, ...input };
}

/** One chip's resting geometry, derived from its label. */
export interface ChipMorph {
  /** Resting chip width in px (before the active chip's barge). */
  width: number;
  /** Chip height in px. */
  height: number;
  /** Font size in px. */
  fontSize: number;
  /** Extra px of width the ACTIVE chip takes (barge × label-based factor). */
  swellPx: number;
}

/**
 * Chip geometry. Very short labels ("01") would make slivers, very long ones
 * ("OBSERVE · PREPROCESS") would eat the row, so the per-character unit is
 * clamped to [3, 14] characters before scaling — the chip still shows the full
 * label; only its padding breathes with the length up to that cap.
 */
export function chipMorph(
  label: string,
  fontPx: number,
  padX: number,
  height: number,
  barge: number,
): ChipMorph {
  const unit = Math.min(Math.max(label.trim().length, 3), 14);
  const width = Math.round(unit * fontPx * 0.72 + padX * 2);
  // Longer labels take more of the barge, capped at the same 14-char unit.
  const swellPx = Math.round((Math.min(label.trim().length, 14) / 14) * barge);
  return { width, height, fontSize: fontPx, swellPx };
}

/** Decay coefficient: higher bounce rings LONGER (smaller k). */
function decayK(bounce: number): number {
  return 2 + 0.6 / (Math.max(bounce, 0.02) + 0.1);
}

/** The wobble state at time t (ms) after a selection. Angles in radians. */
export function jellyWobble(
  tMs: number,
  params: Pick<JellyParams, "jelly" | "bounce" | "stiffness">,
): { x: number; y: number } {
  const { jelly, bounce, stiffness } = params;
  if (jelly <= 0 || tMs <= 0) return { x: 0, y: 0 };
  const w = Math.sqrt(Math.max(stiffness, 1)); // angular frequency, rad/s
  const t = tMs / 1000;
  const amplitude = jelly * 0.12 * Math.exp(-decayK(bounce) * t); // ≤ ~7°
  // Nod (y) slightly heavier than tilt (x), but the combined magnitude is
  // normalised so it never exceeds the amplitude envelope.
  const ux = Math.cos(w * t);
  const uy = Math.sin(w * t) * 1.6;
  const norm = Math.hypot(ux, uy) || 1;
  return { x: (ux / norm) * amplitude, y: (uy / norm) * amplitude };
}

/** True once the wobble at t (ms) is visually finished and the rAF loop can stop. */
export function wobbleSettled(tMs: number, params: Pick<JellyParams, "jelly" | "bounce">): boolean {
  if (params.jelly <= 0) return true;
  const t = tMs / 1000;
  // 0.05° of remaining motion is invisible; stop paying for it.
  return params.jelly * 0.12 * Math.exp(-decayK(params.bounce) * t) < 0.0009;
}

/**
 * Delay before chip `index` joins the wobble that started at `originIndex`.
 * The wave runs outward from the origin and is capped at 8 hops so a long row
 * never holds a chip frozen at the far end.
 */
export function staggerDelay(index: number, originIndex: number, staggerMs: number): number {
  return Math.min(Math.abs(index - originIndex), 8) * staggerMs;
}
