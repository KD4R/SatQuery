"use client";

/**
 * How it works: five steps, scroll-driven, with a sticky illustration that changes
 * as each step reaches the middle of the screen.
 *
 * The steps use the console's own stage names (QUERY, AOI, SENSOR, OBSERVE,
 * PREPROCESS, INFERENCE, CHANGE, EVIDENCE, MONITOR) so that someone who reads this
 * page and then opens the console recognises the timeline they are looking at.
 * The illustrations are diagrams, not data: no figure is drawn on them.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { Reveal } from "../ui";
import { SectionIndex } from "./SectionIndex";

interface Step {
  stages: string;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    stages: "QUERY · AOI",
    title: "Ask, and draw the area.",
    body: "Type the question in plain language and outline where you mean. The request is sanitised and the polygon checked against the analysis budget before anything is fetched.",
  },
  {
    stages: "SENSOR",
    title: "Pick the sensor that can actually see.",
    body: "Optical satellites are blind under cloud, and floods come with cloud. When Sentinel-2 is obscured, Sentinel-1 radar is chosen — and the console tells you why.",
  },
  {
    stages: "OBSERVE · PREPROCESS",
    title: "Find the pass. Admit the gaps.",
    body: "Acquisitions covering the area are selected, calibrated and reprojected. Any part of the area outside the satellite's swath is reported as unanalysed, never filled in.",
  },
  {
    stages: "INFERENCE · CHANGE",
    title: "Segment the water, then subtract the rivers.",
    body: "A U-Net labels water pixel by pixel. The JRC permanent-water layer is removed, so a river that was always there is not counted as a flood.",
  },
  {
    stages: "EVIDENCE · MONITOR",
    title: "Every number ships with its evidence.",
    body: "The answer comes linked to its scenes, model, baseline and caveats — including the fields it could not fill. Then the area can be watched on a schedule.",
  },
];

// Diagram colours follow the page tokens: signal orange for what the system selects
// or answers, blue for water, slate for structure.
const ICE = "#f87010"; // --c-signal
const WATER = "#60a0f8"; // --c-data-b
const VIOLET = "#98a0a8"; // --c-ink-3
const FAINT = "rgba(152,160,168,0.24)";
const PANEL = "#0e0f10";
const ease = [0.16, 1, 0.3, 1] as const;

function Visual({ step }: { step: number }) {
  const reduce = useReducedMotion();
  const draw = (delay = 0) =>
    reduce
      ? {}
      : {
          initial: { pathLength: 0, opacity: 0 },
          animate: { pathLength: 1, opacity: 1 },
          transition: { delay, duration: 1.1, ease },
        };
  const pop = (delay = 0) =>
    reduce
      ? {}
      : {
          initial: { opacity: 0, scale: 0.85 },
          animate: { opacity: 1, scale: 1 },
          transition: { delay, duration: 0.6, ease },
        };

  const text = { fontFamily: "Share Tech Mono, monospace", fontSize: 11, fill: "#b9bec4" };

  return (
    <svg viewBox="0 0 420 420" width="100%" height="100%" role="img" aria-label={STEPS[step]!.title}>
      <defs>
        <pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="7" stroke="rgba(152,160,168,0.35)" strokeWidth="1.2" />
        </pattern>
      </defs>

      {/* ground grid, shared by every step */}
      {Array.from({ length: 11 }, (_, i) => (
        <g key={i} stroke="rgba(152,160,168,0.07)">
          <line x1={20 + i * 38} y1="20" x2={20 + i * 38} y2="400" />
          <line x1="20" y1={20 + i * 38} x2="400" y2={20 + i * 38} />
        </g>
      ))}

      {step === 0 && (
        <g>
          <motion.rect x="40" y="46" width="340" height="44" rx="6" fill={PANEL} stroke={FAINT} {...pop()} />
          <motion.text x="58" y="73" {...text} fill="#ecedee" {...pop(0.1)}>
            › flood extent near the river this week?
          </motion.text>
          <motion.path
            d="M120 170 L250 150 L320 220 L290 320 L150 330 L100 250 Z"
            fill="rgba(248,112,16,0.06)"
            stroke={ICE}
            strokeWidth="2"
            strokeDasharray="0"
            {...draw(0.3)}
          />
          {[
            [120, 170],
            [250, 150],
            [320, 220],
            [290, 320],
            [150, 330],
            [100, 250],
          ].map(([x, y], i) => (
            <motion.circle key={i} cx={x} cy={y} r="5" fill="#080808" stroke={ICE} strokeWidth="2" {...pop(0.4 + i * 0.12)} />
          ))}
          <motion.text x="150" y="365" {...text} {...pop(1.2)}>
            geometry valid · inside budget ✓
          </motion.text>
        </g>
      )}

      {step === 1 && (
        <g>
          <motion.g {...pop()}>
            <rect x="36" y="80" width="160" height="220" rx="8" fill={PANEL} stroke={FAINT} />
            <text x="56" y="112" {...text} fill="#ecedee">Sentinel-2</text>
            <text x="56" y="130" {...text}>optical</text>
            <g fill="rgba(185,190,196,0.26)">
              <ellipse cx="116" cy="200" rx="52" ry="22" />
              <ellipse cx="90" cy="190" rx="28" ry="20" />
              <ellipse cx="140" cy="186" rx="30" ry="22" />
            </g>
            <text x="56" y="272" {...text} fill="#626970">cloud-obscured</text>
            <line x1="56" y1="282" x2="176" y2="282" stroke="#e84040" strokeWidth="1.5" />
          </motion.g>
          <motion.g {...pop(0.25)}>
            <rect x="224" y="80" width="160" height="220" rx="8" fill={PANEL} stroke={ICE} />
            <text x="244" y="112" {...text} fill="#ecedee">Sentinel-1</text>
            <text x="244" y="130" {...text}>C-band radar</text>
            <g fill="rgba(185,190,196,0.14)">
              <ellipse cx="304" cy="200" rx="52" ry="22" />
            </g>
            {[0, 1, 2].map((i) => (
              <motion.path
                key={i}
                d={`M${270 + i * 14} 150 Q ${304} ${200} ${270 + i * 14} 250`}
                stroke={ICE}
                strokeWidth="1.6"
                fill="none"
                {...(reduce
                  ? {}
                  : {
                      initial: { opacity: 0 },
                      animate: { opacity: [0, 1, 0] },
                      transition: { delay: 0.5 + i * 0.25, duration: 1.6, repeat: Infinity },
                    })}
              />
            ))}
            <text x="244" y="272" {...text} fill={ICE}>selected ✓</text>
          </motion.g>
        </g>
      )}

      {step === 2 && (
        <g>
          <motion.path d="M110 120 L300 105 L330 250 L270 330 L120 320 L90 210 Z" fill="url(#hatch)" stroke={FAINT} strokeWidth="1.5" {...pop()} />
          <motion.polygon points="150,40 250,40 360,400 260,400" fill="rgba(248,112,16,0.07)" stroke={ICE} strokeWidth="1" {...pop(0.3)} />
          <clipPath id="swath">
            <polygon points="150,40 250,40 360,400 260,400" />
          </clipPath>
          <motion.path
            d="M110 120 L300 105 L330 250 L270 330 L120 320 L90 210 Z"
            fill="rgba(96,160,248,0.28)"
            stroke={WATER}
            strokeWidth="2"
            clipPath="url(#swath)"
            {...pop(0.6)}
          />
          <motion.text x="40" y="376" {...text} {...pop(0.9)}>
            hatched: outside the swath — reported, not guessed
          </motion.text>
        </g>
      )}

      {step === 3 && (
        <g>
          {Array.from({ length: 12 * 12 }, (_, i) => {
            const c = i % 12;
            const r = Math.floor(i / 12);
            // A fixed, hand-drawn water shape: a broad flooded plain and a river.
            const d = Math.hypot(c - 5.5 + Math.sin(r / 2) * 1.5, (r - 6) * 0.7);
            const water = d < 3.6;
            const river = Math.abs(c - (3 + r * 0.55)) < 0.6;
            return (
              <motion.rect
                key={i}
                x={50 + c * 27}
                y={50 + r * 27}
                width="24"
                height="24"
                rx="2"
                fill={water ? "rgba(96,160,248,0.8)" : river ? "rgba(152,160,168,0.5)" : "rgba(152,160,168,0.06)"}
                {...(reduce || (!water && !river)
                  ? {}
                  : {
                      initial: { opacity: 0 },
                      animate: river ? { opacity: [0, 1, 1, 0.15] } : { opacity: 1 },
                      transition: river
                        ? { duration: 2.4, times: [0, 0.2, 0.7, 1], delay: 0.2 }
                        : { delay: 0.2 + (c + r) * 0.03, duration: 0.4 },
                    })}
              />
            );
          })}
          <motion.text x="50" y="395" {...text} {...pop(1.6)}>
            <tspan fill={WATER}>■ water</tspan>
            <tspan dx="14" fill={VIOLET}>■ permanent river, subtracted</tspan>
          </motion.text>
        </g>
      )}

      {step === 4 && (
        <g>
          {(
            [
              [210, 210, "ANSWER", true],
              [90, 110, "scene", false],
              [330, 110, "model", false],
              [70, 270, "baseline", false],
              [350, 270, "caveats", false],
              [210, 355, "NOT AVAILABLE", false],
            ] as const
          ).map(([x, y], i) =>
            i === 0 ? null : (
              <motion.line key={`e${i}`} x1={210} y1={210} x2={x} y2={y} stroke={FAINT} strokeWidth="1.2" {...draw(0.15 * i)} />
            ),
          )}
          {(
            [
              [210, 210, "ANSWER", true],
              [90, 110, "scene", false],
              [330, 110, "model", false],
              [70, 270, "baseline", false],
              [350, 270, "caveats", false],
              [210, 355, "NOT AVAILABLE", false],
            ] as const
          ).map(([x, y, label, main], i) => (
            <motion.g key={label} {...pop(0.2 + i * 0.12)}>
              <circle cx={x} cy={y} r={main ? 34 : 24} fill={PANEL} stroke={main ? ICE : label === "NOT AVAILABLE" ? "#626970" : VIOLET} strokeWidth={main ? 2 : 1.4} strokeDasharray={label === "NOT AVAILABLE" ? "4 4" : undefined} />
              <text x={x} y={y + 4} textAnchor="middle" {...text} fontSize={main ? 11 : 9.5} fill={main ? "#ecedee" : "#b9bec4"}>
                {label === "NOT AVAILABLE" ? "N/A" : label}
              </text>
            </motion.g>
          ))}
          <motion.text x="120" y="400" {...text} {...pop(1.1)}>
            a gap is a node too — marked, not hidden
          </motion.text>
        </g>
      )}
    </svg>
  );
}

export function HowItWorks() {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) setActive(Number((e.target as HTMLElement).dataset.i));
        }
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    refs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <section id="how" className="sq-section">
      <div className="sq-wrap">
        <Reveal className="sq-section-head">
          <SectionIndex n={2} label="How it works" />
          <h2 className="sq-h2">
            From a sentence <span className="is-quiet">to a map you can defend.</span>
          </h2>
          <p className="sq-sub">
            Five steps, the same ones the console&rsquo;s mission timeline shows you as it runs.
          </p>
        </Reveal>

        <div className="sq-how">
          <div className="sq-panel sq-how-visual">
            <AnimatePresence mode="wait">
              <motion.div
                key={active}
                style={{ width: "100%", height: "100%" }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
              >
                <Visual step={active} />
              </motion.div>
            </AnimatePresence>
          </div>

          <div className="sq-how-steps">
            {STEPS.map((s, i) => (
              <div
                key={s.title}
                ref={(el) => {
                  refs.current[i] = el;
                }}
                data-i={i}
                className={`sq-step${i === active ? " is-active" : ""}`}
              >
                <span className="sq-step-n">0{i + 1}</span>
                <div className="sq-step-stage">{s.stages}</div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
