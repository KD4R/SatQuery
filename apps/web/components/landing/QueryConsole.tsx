"use client";

/**
 * The example query, shown as the console's command line: a header, the question
 * being typed, and the stages the question will run through.
 *
 * The questions are examples of what a person can type, not recorded runs; the
 * header says so. The stage names in the footer are the console's own.
 */

import { useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";

const EXAMPLES = [
  "Map new flood water along the Brahmaputra near Nagaon.",
  "Where has water spread in Assam since the last radar pass?",
  "Show the flooded area — and tell me what you couldn't see.",
];

const STAGES = ["AOI", "SENSOR", "OBSERVE", "INFERENCE", "EVIDENCE"];

function useTypewriter(lines: string[]) {
  const reduce = useReducedMotion();
  const [state, setState] = useState({ line: 0, chars: lines[0]!.length });

  useEffect(() => {
    if (reduce) return;
    let line = 0;
    let chars = 0;
    let deleting = false;
    let timer: ReturnType<typeof setTimeout>;
    setState({ line: 0, chars: 0 });
    const tick = () => {
      const full = lines[line]!;
      if (!deleting) {
        chars += 1;
        setState({ line, chars });
        if (chars >= full.length) {
          deleting = true;
          timer = setTimeout(tick, 2800);
          return;
        }
        timer = setTimeout(tick, 30 + (full.charCodeAt(chars - 1) % 5) * 8);
      } else {
        chars -= 3;
        if (chars <= 0) {
          chars = 0;
          deleting = false;
          line = (line + 1) % lines.length;
        }
        setState({ line, chars });
        timer = setTimeout(tick, chars === 0 ? 380 : 14);
      }
    };
    timer = setTimeout(tick, 1400);
    return () => clearTimeout(timer);
  }, [lines, reduce]);

  return lines[state.line]!.slice(0, state.chars);
}

export function QueryConsole() {
  const typed = useTypewriter(EXAMPLES);

  return (
    <div className="sq-console" role="group" aria-label="Example question">
      <div className="sq-console-head">
        <b>Query</b>
        <span className="sq-console-state">
          <i aria-hidden="true" />
          Plain language · example
        </span>
      </div>
      <div className="sq-console-body">
        <span className="sq-console-prompt" aria-hidden="true">
          ›
        </span>
        <span>
          <span aria-live="off">{typed}</span>
          <span className="sq-caret" aria-hidden="true" />
        </span>
      </div>
      <div className="sq-console-foot" aria-label="Stages the question runs through">
        <em>Runs</em>
        {STAGES.map((s, i) => (
          <span key={s}>
            {s}
            {i < STAGES.length - 1 ? <em> →</em> : null}
          </span>
        ))}
      </div>
    </div>
  );
}
