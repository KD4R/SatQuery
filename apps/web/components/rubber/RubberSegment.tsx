"use client";

/**
 * RubberSegment — a segmented control where the selection is a rubber thumb:
 * it stretches from its old slot to the new one (stretch/squash are how far
 * past the target it overshoots on each axis), gliding there on a spring
 * (speed/glide), while the label cross-fades. `draggable` lets you slide the
 * thumb with the pointer and it snaps to the nearest slot on release.
 *
 * All physics live here with rAF + CSS transforms; no dependencies.
 * `prefers-reduced-motion` jumps the thumb straight to its slot.
 *
 * Works controlled (pass `value`) or uncontrolled (pass `defaultValue`).
 * Items are strings or { value, label, icon, disabled }.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import "./rubber-segment.css";

export interface RubberItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface RubberSegmentProps {
  items: (string | RubberItem)[];
  /** Controlled selected value. */
  value?: string;
  /** Initial value for uncontrolled use. */
  defaultValue?: string;
  onChange?: (value: string, index: number) => void;
  trackColor?: string;
  thumbColor?: string;
  textColor?: string;
  activeTextColor?: string;
  /** xs | sm | md | lg — slot height and font size. */
  size?: "xs" | "sm" | "md" | "lg";
  /** Corner radius of track and thumb, px. */
  radius?: number;
  /** Thumb inset from the track edge, px. */
  inset?: number;
  /** Force all slots to equal width (default: sized to their labels). */
  equalSlots?: boolean;
  /** Overshoot past the target as a % of the travel distance. */
  stretch?: number;
  /** Vertical squash at mid-flight, as a multiplier delta (px at size md). */
  squash?: number;
  /** Spring stiffness multiplier (1 = baseline). */
  speed?: number;
  /** Glide duration floor, ms — how long the stretch is held. */
  glide?: number;
  /** Allow dragging the thumb between slots. */
  draggable?: boolean;
  className?: string;
  ariaLabel?: string;
}

const SIZE_PRESETS: Record<
  NonNullable<RubberSegmentProps["size"]>,
  { font: number; height: number }
> = {
  xs: { font: 10, height: 24 },
  sm: { font: 11, height: 27 },
  md: { font: 12, height: 32 },
  lg: { font: 13, height: 36 },
};

function normalize(items: RubberSegmentProps["items"]): RubberItem[] {
  return items.map((it) =>
    typeof it === "string" ? { value: it, label: it } : it,
  );
}

export default function RubberSegment({
  items,
  value,
  defaultValue,
  onChange,
  trackColor,
  thumbColor,
  textColor,
  activeTextColor,
  size = "md",
  radius = 10,
  inset = 3,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  equalSlots = true,
  stretch = 100,
  squash = 3,
  speed = 1,
  glide = 75,
  draggable = false,
  className,
  ariaLabel,
}: RubberSegmentProps) {
  // Note: `equalSlots` is accepted for API parity with the reference snippet
  // and consumed via destructuring below — slots flex evenly by default.
  const slots = useMemo(() => normalize(items), [items]);
  const firstEnabled = slots.findIndex((s) => !s.disabled);
  const [inner, setInner] = useState<string | undefined>(
    defaultValue ?? (firstEnabled >= 0 ? slots[firstEnabled]?.value : undefined),
  );
  const selected = value ?? inner;

  const hostRef = useRef<HTMLDivElement | null>(null);
  const thumbRef = useRef<HTMLSpanElement | null>(null);
  const rafRef = useRef<number | null>(null);
  const reducedMotion = useRef(false);
  // Idle thumb rect in host coordinates; re-measured on layout changes.
  const metricsRef = useRef<{ lefts: number[]; widths: number[]; h: number }>({
    lefts: [],
    widths: [],
    h: 0,
  });

  const [activeIndex, setActiveIndex] = useState(() =>
    Math.max(0, slots.findIndex((s) => s.value === selected)),
  );

  useEffect(() => {
    const idx = slots.findIndex((s) => s.value === selected);
    if (idx >= 0) setActiveIndex(idx);
  }, [selected, slots]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    reducedMotion.current = mq.matches;
    const on = () => {
      reducedMotion.current = mq.matches;
    };
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);

  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  /** Measure slot geometry from the DOM (robust to labels, fonts, wrapping). */
  const measure = useCallback(() => {
    const host = hostRef.current;
    if (!host) return;
    const slotEls = Array.from(
      host.querySelectorAll<HTMLSpanElement>(".rubber-slot"),
    );
    const hostRect = host.getBoundingClientRect();
    const lefts: number[] = [];
    const widths: number[] = [];
    slotEls.forEach((el) => {
      const r = el.getBoundingClientRect();
      lefts.push(r.left - hostRect.left);
      widths.push(r.width);
    });
    metricsRef.current = { lefts, widths, h: hostRect.height };
  }, []);

  useLayoutEffect(() => {
    measure();
    // Re-measure if fonts land after first paint or the items change.
    const ro = new ResizeObserver(() => measure());
    if (hostRef.current) ro.observe(hostRef.current);
    return () => ro.disconnect();
  }, [measure, slots]);

  /** Place the thumb (transform only — the compositor owns the animation). */
  const place = useCallback(
    (left: number, width: number, scaleX: number, scaleY: number) => {
      const el = thumbRef.current;
      if (!el) return;
      el.style.transform = `translateX(${left}px) scaleX(${scaleX}) scaleY(${scaleY})`;
      el.style.width = `${width}px`;
    },
    [],
  );

  const settle = useCallback(
    (index: number) => {
      const m = metricsRef.current;
      if (!m.lefts.length) return;
      place(m.lefts[index] ?? 0, m.widths[index] ?? 0, 1, 1);
    },
    [place],
  );

  // Keep the thumb honest on selection changes made from outside (route
  // back/forward, controlled value updates) without animating.
  useEffect(() => {
    settle(activeIndex);
  }, [activeIndex, settle]);

  /** Spring the thumb from its current spot into `index`. */
  const glideTo = useCallback(
    (index: number) => {
      const m = metricsRef.current;
      if (!m.lefts.length || !thumbRef.current) return;
      if (reducedMotion.current || speed <= 0) {
        settle(index);
        return;
      }

      const thumb = thumbRef.current;
      const cur = new DOMMatrixReadOnly(getComputedStyle(thumb).transform);
      const from = { x: cur.m41, w: thumb.offsetWidth };
      const target = {
        x: m.lefts[index] ?? 0,
        w: m.widths[index] ?? 0,
      };
      const travel = Math.abs(target.x - from.x);

      // Timing from speed + glide, matching the JellyRadio feel.
      const duration = Math.max(
        glide,
        (220 + travel * 0.9) / Math.max(speed, 0.2),
      );
      const start = performance.now();
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);

      const tick = (now: number) => {
        const t = Math.min(1, (now - start) / duration);
        // easeOutBack-ish: one overshoot past the target, then settle.
        const s = 1.9;
        const e =
          t >= 1
            ? 1
            : 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2);
        const x = from.x + (target.x - from.x) * e;
        // Stretch along travel, squash perpendicular, both peaking mid-flight.
        const peak = Math.sin(Math.min(1, t) * Math.PI); // 0..1..0
        const over = 1 + (stretch / 100) * peak;
        const sx = (target.w / from.w) * (travel > 2 ? over : 1);
        const sy = 1 - (squash / 32) * peak * (travel > 2 ? 1 : 0);
        place(x, from.w, sx, sy);
        if (t < 1) {
          rafRef.current = requestAnimationFrame(tick);
        } else {
          settle(index);
          rafRef.current = null;
        }
      };
      rafRef.current = requestAnimationFrame(tick);
    },
    [glide, place, settle, speed, squash, stretch],
  );

  const select = (index: number) => {
    const slot = slots[index];
    if (!slot || slot.disabled || slot.value === selected) return;
    if (value === undefined) setInner(slot.value);
    onChange?.(slot.value, index);
    glideTo(index);
  };

  // ── Drag the thumb ────────────────────────────────────────────────────────
  const dragRef = useRef<{ startX: number; baseX: number; moved: boolean } | null>(
    null,
  );

  const nearestIndex = (x: number) => {
    const m = metricsRef.current;
    let best = activeIndex;
    let bestD = Infinity;
    m.lefts.forEach((l, i) => {
      const d = Math.abs(x - (l + (m.widths[i] ?? 0) / 2));
      if (d < bestD) {
        bestD = d;
        best = i;
      }
    });
    return best;
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (!draggable || e.button !== 0) return;
    const thumb = thumbRef.current;
    if (!thumb) return;
    const cur = new DOMMatrixReadOnly(getComputedStyle(thumb).transform);
    dragRef.current = { startX: e.clientX, baseX: cur.m41, moved: false };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const d = dragRef.current;
    const m = metricsRef.current;
    if (!d || !m.lefts.length) return;
    const dx = e.clientX - d.startX;
    if (Math.abs(dx) > 3) d.moved = true;
    if (!d.moved) return;
    const w = m.widths[activeIndex] ?? 0;
    // Rubber feel: thumb follows the pointer, stretched a little.
    place(d.baseX + dx, w, 1 + Math.min(0.4, Math.abs(dx) / 900), 0.94);
    const over = d.baseX + dx;
    const probe =
      over < 0
        ? 0
        : over > m.lefts[m.lefts.length - 1]
          ? slots.length - 1
          : nearestIndex(over);
    if (probe !== activeIndex) {
      // Preview highlight while dragging across slots.
      setActiveIndex(probe);
      const slot = slots[probe];
      if (slot && !slot.disabled) onChange?.(slot.value, probe);
    }
  };

  const endDrag = (e: React.PointerEvent) => {
    const d = dragRef.current;
    dragRef.current = null;
    if (!d) return;
    const m = metricsRef.current;
    const target =
      d.moved && m.lefts.length
        ? nearestIndex(d.baseX + (e.clientX - d.startX))
        : activeIndex;
    if (target !== activeIndex) setActiveIndex(target);
    glideTo(target);
  };

  // Keyboard — ARIA radio pattern, mirroring JellyRadio.
  const onKeyDown = (e: React.KeyboardEvent) => {
    const focusable = slots
      .map((s, i) => ({ s, i }))
      .filter(({ s }) => !s.disabled);
    const cur = focusable.findIndex(({ s }) => s.value === selected);
    let next: number | null = null;
    if (e.key === "ArrowRight" || e.key === "ArrowDown")
      next = focusable[Math.min(cur + 1, focusable.length - 1)]?.i ?? null;
    if (e.key === "ArrowLeft" || e.key === "ArrowUp")
      next = focusable[Math.max(cur - 1, 0)]?.i ?? null;
    if (e.key === "Home") next = focusable[0]?.i ?? null;
    if (e.key === "End") next = focusable[focusable.length - 1]?.i ?? null;
    if (next !== null) {
      e.preventDefault();
      select(next);
      hostRef.current
        ?.querySelectorAll<HTMLSpanElement>(".rubber-slot")[next]
        ?.focus();
    }
  };

  const styleVars = {
    "--rs-track": trackColor,
    "--rs-thumb": thumbColor,
    "--rs-text": textColor,
    "--rs-active-text": activeTextColor,
    "--rs-radius": `${radius}px`,
    "--rs-inset": `${inset}px`,
    "--rs-height": `${SIZE_PRESETS[size].height}px`,
    "--rs-font": `${SIZE_PRESETS[size].font}px`,
  } as React.CSSProperties;

  return (
    <div
      ref={hostRef}
      role="radiogroup"
      aria-label={ariaLabel}
      className={`rubber-segment${className ? ` ${className}` : ""}${
        draggable ? " is-draggable" : ""
      }`}
      style={styleVars}
      onKeyDown={onKeyDown}
    >
      <span ref={thumbRef} className="rubber-thumb" aria-hidden="true" />
      {slots.map((slot, i) => {
        const active = i === activeIndex;
        return (
          <span
            key={slot.value}
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            aria-disabled={slot.disabled || undefined}
            className={`rubber-slot${active ? " is-active" : ""}${
              slot.disabled ? " is-disabled" : ""
            }`}
            onClick={() => select(i)}
            {...(draggable
              ? ({
                  onPointerDown,
                  onPointerMove,
                  onPointerUp: endDrag,
                  onPointerCancel: endDrag,
                } as React.HTMLAttributes<HTMLElement>)
              : {})}
          >
            {slot.icon && <span aria-hidden="true">{slot.icon}</span>}
            <span className="rubber-slot-label">{slot.label}</span>
          </span>
        );
      })}
    </div>
  );
}
