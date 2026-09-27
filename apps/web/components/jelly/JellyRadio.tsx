"use client";

/**
 * JellyRadio — a squishy segmented control.
 *
 * A row of chips where the selected one "barges": it grows (swell/barge), the
 * neighbours dip (shrink), and a damped spring wobble (jelly/bounce/stiffness)
 * ripples outward from the selection point (stagger). All the numbers that
 * shape the feel are props; the physics lives in lib/jelly-fx so it can be
 * unit-tested without React.
 *
 * Works controlled (pass `value`) or uncontrolled (pass `defaultValue`).
 * Items are plain strings or { value, label, icon, disabled } objects.
 * `prefers-reduced-motion` is honoured: the wobble never starts and the CSS
 * falls back to plain colour transitions.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  chipMorph,
  jellyWobble,
  staggerDelay,
  wobbleSettled,
  withJellyDefaults,
  type JellyParamsInput,
} from "../../lib/jelly-fx";
import "./jelly-radio.css";

export interface JellyItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface JellyRadioProps {
  items: (string | JellyItem)[];
  /** Controlled selected value. */
  value?: string;
  /** Initial value for uncontrolled use. */
  defaultValue?: string;
  onChange?: (value: string, index: number) => void;
  chipColor?: string;
  activeColor?: string;
  textColor?: string;
  activeTextColor?: string;
  /** xs | sm | md | lg — sets chip height and font size. */
  size?: "xs" | "sm" | "md" | "lg";
  /** Gap between chips, px. */
  gap?: number;
  /** Chip corner radius, px. */
  radius?: number;
  /** Physics knobs — see lib/jelly-fx. */
  swell?: number;
  barge?: number;
  shrink?: number;
  jelly?: number;
  bounce?: number;
  stagger?: number;
  stiffness?: number;
  className?: string;
  ariaLabel?: string;
}

const SIZE_PRESETS: Record<
  NonNullable<JellyRadioProps["size"]>,
  { font: number; padX: number; height: number }
> = {
  xs: { font: 10, padX: 9, height: 24 },
  sm: { font: 11, padX: 10, height: 27 },
  md: { font: 12, padX: 12, height: 30 },
  lg: { font: 13, padX: 14, height: 34 },
};

function normalizeItems(items: JellyRadioProps["items"]): JellyItem[] {
  return items.map((it) =>
    typeof it === "string" ? { value: it, label: it } : it,
  );
}

export default function JellyRadio({
  items,
  value,
  defaultValue,
  onChange,
  chipColor,
  activeColor,
  textColor,
  activeTextColor,
  size = "md",
  gap = 8,
  radius = 18,
  swell,
  barge,
  shrink,
  jelly,
  bounce,
  stagger,
  stiffness,
  className,
  ariaLabel,
}: JellyRadioProps) {
  const chips = useMemo(() => normalizeItems(items), [items]);
  const firstEnabled = chips.findIndex((c) => !c.disabled);
  const [inner, setInner] = useState<string | undefined>(
    defaultValue ?? (firstEnabled >= 0 ? chips[firstEnabled]?.value : undefined),
  );
  const selected = value ?? inner;

  const params = useMemo(
    () =>
      withJellyDefaults({
        swell,
        barge,
        shrink,
        jelly,
        bounce,
        stagger,
        stiffness,
      } satisfies JellyParamsInput),
    [swell, barge, shrink, jelly, bounce, stagger, stiffness],
  );

  const preset = SIZE_PRESETS[size];
  const hostRef = useRef<HTMLDivElement | null>(null);
  const runIdRef = useRef(0);
  const originRef = useRef(0);
  const startTimeRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const reducedMotion = useRef(false);
  const [selectedAt, setSelectedAt] = useState<{ index: number } | null>(null);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedMotion.current = mq.matches;
    const onChangeMq = () => {
      reducedMotion.current = mq.matches;
    };
    mq.addEventListener("change", onChangeMq);
    return () => mq.removeEventListener("change", onChangeMq);
  }, []);

  // Kill any running rAF loop on unmount.
  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  const geometry = useMemo(
    () =>
      chips.map((c) =>
        chipMorph(c.label, preset.font, preset.padX, preset.height, params.barge),
      ),
    [chips, preset, params.barge],
  );

  // The wobble loop: rAF drives per-chip rotateX/rotateY through CSS custom
  // properties so the compositor stays in charge of the paint.
  const runWobble = useCallback(
    (seq: number) => {
      if (reducedMotion.current || params.jelly <= 0) return;
      const host = hostRef.current;
      if (!host) return;
      const chipEls = Array.from(
        host.querySelectorAll<HTMLButtonElement>(".jelly-chip"),
      );
      if (chipEls.length === 0) return;

      const tick = (now: number) => {
        if (seq !== runIdRef.current) return; // a newer selection took over
        const t = now - startTimeRef.current;
        chipEls.forEach((el, i) => {
          const local = t - staggerDelay(i, originRef.current, params.stagger);
          if (local <= 0) return; // the wave has not reached this chip yet
          const w = jellyWobble(local, params);
          el.style.setProperty("--jr-rot-x", `${(w.y * 180) / Math.PI}deg`);
          el.style.setProperty("--jr-rot-y", `${(w.x * 180) / Math.PI}deg`);
        });
        if (wobbleSettled(t, params) && t > params.stagger * 8 + 400) {
          chipEls.forEach((el) => {
            el.style.setProperty("--jr-rot-x", "0deg");
            el.style.setProperty("--jr-rot-y", "0deg");
          });
          rafRef.current = null;
          return;
        }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    },
    [params],
  );

  const select = (index: number, chip: JellyItem) => {
    if (chip.disabled || chip.value === selected) return;
    if (value === undefined) setInner(chip.value);
    onChange?.(chip.value, index);
    runIdRef.current += 1;
    originRef.current = index;
    startTimeRef.current = performance.now();
    setSelectedAt({ index });
    runWobble(runIdRef.current);
  };

  // Keyboard: arrows move selection, Home/End jump — ARIA radio pattern.
  const onKeyDown = (e: React.KeyboardEvent) => {
    const focusable = chips
      .map((c, i) => ({ c, i }))
      .filter(({ c }) => !c.disabled);
    const currentIndex = focusable.findIndex(({ c }) => c.value === selected);
    let next: number | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowDown")
      next = focusable[Math.min(currentIndex + 1, focusable.length - 1)]?.i ?? null;
    if (e.key === "ArrowLeft" || e.key === "ArrowUp")
      next = focusable[Math.max(currentIndex - 1, 0)]?.i ?? null;
    if (e.key === "Home") next = focusable[0]?.i ?? null;
    if (e.key === "End") next = focusable[focusable.length - 1]?.i ?? null;
    if (next !== null) {
      e.preventDefault();
      select(next, chips[next]);
      hostRef.current
        ?.querySelectorAll<HTMLButtonElement>(".jelly-chip")
        [next]?.focus();
    }
  };

  // Root-level CSS custom properties (palette, sizes, physics timing).
  const styleVars = {
    "--jr-chip": chipColor,
    "--jr-active": activeColor,
    "--jr-text": textColor,
    "--jr-active-text": activeTextColor,
    "--jr-gap": `${gap}px`,
    "--jr-radius": `${radius}px`,
    "--jr-font": `${preset.font}px`,
    "--jr-height": `${preset.height}px`,
    "--jr-shrink": `${params.shrink}`,
    // Time for one visible ring of the wobble, from bounce/stiffness.
    "--jr-settle": `${Math.round(
      1200 / Math.sqrt(Math.max(params.stiffness, 1)) + params.bounce * 400,
    )}`,
  } as React.CSSProperties;

  return (
    <div
      ref={hostRef}
      role="radiogroup"
      aria-label={ariaLabel}
      className={`jelly-radio${className ? ` ${className}` : ""}`}
      style={styleVars}
      onKeyDown={onKeyDown}
    >
      {chips.map((chip, i) => {
        const active = chip.value === selected;
        const g = geometry[i];
        const shrunk =
          selectedAt !== null && !active && Math.abs(i - selectedAt.index) === 1;
        return (
          <button
            key={chip.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={chip.disabled}
            tabIndex={active ? 0 : -1}
            className={`jelly-chip${active ? " is-active" : ""}${
              shrunk ? " is-shrunk" : ""
            }`}
            style={{
              // Active chip: resting width + barge (label-weighted) + swell
              // (fraction of its own resting width).
              width: active
                ? g.width + g.swellPx + Math.round(g.width * params.swell)
                : g.width,
            }}
            onClick={() => select(i, chip)}
          >
            {chip.icon && <span aria-hidden="true">{chip.icon}</span>}
            <span className="jelly-chip-label">{chip.label}</span>
          </button>
        );
      })}
    </div>
  );
}
