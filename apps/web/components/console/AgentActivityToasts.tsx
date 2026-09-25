"use client";

/**
 * Live agent activity toasts (P5 Phase C, PRD §2C).
 *
 * Non-intrusive by contract: bottom-right, auto-expiring, one at a time in
 * view, each dismissible. The PRD's example — "⚠ Optical and SAR sensors
 * disagree on flood extent. Acquiring additional radar observation..." — is
 * rendered as a warning tone with the server's reason as plain text.
 *
 * A03: every string here came through envelopeToAgentEvent's type gates and is
 * rendered as a React text node. No dangerouslySetInnerHTML exists in this
 * component, so no sanitiser has to be right for the DOM to stay safe.
 *
 * a11y: the stack is an aria-live polite region so screen readers hear the
 * agent without it interrupting them; each toast is a status with its own
 * dismiss control.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef } from "react";

import type { AgentEvent, AgentEventType } from "../../lib/ws/useMissionEvents";

const GLYPH: Record<AgentEventType, string> = {
  SENSOR_DISAGREEMENT: "⚠",
  SENSOR_AGREEMENT: "✓",
  ACQUIRING_EVIDENCE: "◌",
  AGENT_THOUGHT: "▸",
};

/** How long a toast stays before retiring itself. */
const TOAST_TTL_MS = 7_000;

function ToastItem({ event, onDismiss }: { event: AgentEvent; onDismiss: (id: string) => void }) {
  const reduce = useReducedMotion();

  // onDismiss reaches the timer through a ref: the expiry must depend on the
  // toast's own lifetime, not on the parent re-rendering (a new callback
  // identity mid-run would silently reset every toast's clock).
  const dismissRef = useRef(onDismiss);
  useEffect(() => {
    dismissRef.current = onDismiss;
  }, [onDismiss]);

  // Auto-expire. Reduced motion skips the animation, not the expiry — a toast
  // that lingers forever is exactly the intrusion the PRD rules out.
  useEffect(() => {
    const t = setTimeout(() => dismissRef.current(event.id), TOAST_TTL_MS);
    return () => clearTimeout(t);
  }, [event.id]);

  return (
    <motion.div
      role="status"
      className={`atoast atoast-${event.type.toLowerCase()}`}
      initial={reduce ? false : { opacity: 0, x: 18 }}
      animate={{ opacity: 1, x: 0 }}
      exit={reduce ? { opacity: 1 } : { opacity: 0, x: 18 }}
      transition={{ duration: reduce ? 0 : 0.16 }}
    >
      <span className="atoast-glyph" aria-hidden="true">
        {GLYPH[event.type]}
      </span>
      <p className="atoast-text">{event.message}</p>
      <button
        type="button"
        className="atoast-dismiss"
        onClick={() => onDismiss(event.id)}
        aria-label={`Dismiss: ${event.message}`}
      >
        ✕
      </button>
    </motion.div>
  );
}

export function AgentActivityToasts({
  events,
  onDismiss,
}: {
  events: AgentEvent[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div className="atoasts" aria-live="polite" aria-relevant="additions text">
      <AnimatePresence initial={false}>
        {events.map((e) => (
          <ToastItem key={e.id} event={e} onDismiss={onDismiss} />
        ))}
      </AnimatePresence>
    </div>
  );
}

export default AgentActivityToasts;
