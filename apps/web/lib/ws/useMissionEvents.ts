"use client";

/**
 * Live agent events (P5 Phase C, PRD §2C) — the console listening to the
 * investigator, not polling a dashboard.
 *
 * Wires to the gateway's mission WebSocket (P1-08): WS /ws/v1/missions/{id},
 * JWT as ?token= because the browser WebSocket API cannot set headers. The
 * token comes from the same module-scoped variable every other call uses —
 * never from storage (A02) — so in live mode the socket is simply not opened
 * until the operator has authenticated, and the URL is built only from the
 * location origin plus a validated mission id.
 *
 * Envelopes are validated before they reach React state (A03 defence in
 * depth): unknown event types are dropped, and the narrative strings are kept
 * as strings. Nothing from the socket is ever turned into HTML downstream.
 *
 * In demo mode the hook is a no-op: the demo's honesty depends on nothing
 * opening a socket on its behalf.
 */

import { useEffect, useRef, useState } from "react";

import { getAccessToken } from "../api/gateway";

/** The event types the UI understands. Anything else is dropped, not guessed. */
export type AgentEventType =
  | "SENSOR_DISAGREEMENT"
  | "SENSOR_AGREEMENT"
  | "ACQUIRING_EVIDENCE"
  | "AGENT_THOUGHT";

export interface AgentEvent {
  id: string;
  type: AgentEventType;
  /** Server-authored narrative. Rendered as text only, never HTML. */
  message: string;
  at: string;
}

interface EnvelopeShape {
  event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  trace_id: string | null;
}

const MAX_EVENTS = 4;
const BACKOFF_MS = [1000, 2000, 4000, 8000];

/** True when the value can only have come from a string, never an object. */
function isText(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

function toAgentEvent(env: EnvelopeShape): AgentEvent | null {
  const p = env.payload;
  switch (env.event_type) {
    case "SENSOR_DISAGREEMENT": {
      const reason = isText(p.reason) ? p.reason : null;
      if (!reason) return null;
      // The agreement counterpart is its own UI event: it retires the warning
      // toast instead of raising one.
      return {
        id: env.event_id,
        type: p.disagreement === false ? "SENSOR_AGREEMENT" : "SENSOR_DISAGREEMENT",
        message: reason,
        at: new Date().toISOString(),
      };
    }
    case "ACQUIRING_EVIDENCE": {
      if (!isText(p.reason)) return null;
      return { id: env.event_id, type: "ACQUIRING_EVIDENCE", message: p.reason, at: new Date().toISOString() };
    }
    case "AGENT_THOUGHT": {
      if (!isText(p.text)) return null;
      return { id: env.event_id, type: "AGENT_THOUGHT", message: p.text, at: new Date().toISOString() };
    }
    default:
      return null;
  }
}

/**
 * Envelope → UI event. Exported for pure unit tests: the security-relevant
 * part of the client is this mapping, so it is testable without a socket.
 */
export function envelopeToAgentEvent(env: EnvelopeShape): AgentEvent | null {
  return toAgentEvent(env);
}

export type EventsStatus = "idle" | "connecting" | "open" | "closed";

/**
 * Subscribes to the mission's live agent events. `enabled` gates the socket —
 * the console turns it on only for an authenticated live run.
 */
export function useMissionEvents(missionId: string | null, enabled: boolean) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [status, setStatus] = useState<EventsStatus>("idle");
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(0);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const disposedRef = useRef(false);

  useEffect(() => {
    disposedRef.current = false;
    if (!missionId || !enabled) {
      // Idle/closed keeps already-delivered events on screen — the run ended,
      // but the operator should still see what the agent said. A *new* run
      // clears the stack below, when a fresh mission id arrives.
      setStatus("idle");
      return;
    }

    // Mission ids come from our own data, but the socket URL is infra-adjacent:
    // only a conservative charset may reach it (A10 — no injection surface).
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(missionId)) {
      setStatus("closed");
      return;
    }

    setStatus("connecting");
    setEvents([]); // a new subscription window starts empty

    const clearTimers = () => {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    };

    const connect = () => {
      if (disposedRef.current) return;
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const token = getAccessToken();
      const url =
        `${proto}//${window.location.host}/ws/v1/missions/${encodeURIComponent(missionId)}` +
        (token ? `?token=${encodeURIComponent(token)}` : "");

      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        setStatus("closed");
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        if (disposedRef.current) return;
        backoffRef.current = 0;
        setStatus("open");
      };

      ws.onmessage = (message: MessageEvent) => {
        if (disposedRef.current) return;
        let parsed: unknown = null;
        try {
          parsed = JSON.parse(String(message.data));
        } catch {
          return; // a non-JSON frame is protocol noise, not an event
        }
        if (!parsed || typeof parsed !== "object") return;
        const env = parsed as Partial<EnvelopeShape>;
        if (
          typeof env.event_id !== "string" ||
          typeof env.event_type !== "string" ||
          env.payload === null ||
          typeof env.payload !== "object"
        ) {
          return;
        }
        // "connected"/"status_update"/"done" frames are the P1-08 status
        // protocol; toAgentEvent returns null for them and they are dropped.
        const event = toAgentEvent(env as EnvelopeShape);
        if (!event) return;
        setEvents((prev) => [...prev.slice(-(MAX_EVENTS - 1)), event]);
      };

      ws.onclose = () => {
        if (disposedRef.current) return;
        setStatus("closed");
        // Backoff reconnect: 1s → 8s, capped. No storm when the gateway is down.
        const wait = BACKOFF_MS[Math.min(backoffRef.current, BACKOFF_MS.length - 1)];
        backoffRef.current += 1;
        timersRef.current.push(setTimeout(connect, wait));
      };

      ws.onerror = () => {
        try {
          ws.close();
        } catch {
          /* already closing */
        }
      };
    };

    connect();

    return () => {
      disposedRef.current = true;
      clearTimers();
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        ws.onclose = null;
        ws.close();
      }
      // Deliberately no setEvents([]) here: teardown keeps history so the
      // operator can read what the agent said after the run settles.
      setStatus("idle");
    };
  }, [missionId, enabled]);

  /** Dismiss one toast. */
  const dismiss = (id: string) => {
    setEvents((prev) => prev.filter((e) => e.id !== id));
  };

  return { events, status, dismiss };
}
