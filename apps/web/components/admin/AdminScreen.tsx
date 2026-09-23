"use client";

/**
 * Admin, security and accessibility surface (P5-15).
 *
 * This page is where the security posture becomes inspectable instead of being a
 * claim in a PR description. Each control states what the frontend actually does
 * and, where a control is the backend's responsibility, says so rather than
 * implying the browser enforces it.
 *
 * The session block is deliberately blunt about token handling: the token is a
 * module variable that dies with the tab. That is the PRD's rule, and a user who
 * wonders why they are signed out on refresh deserves to find the answer here.
 */

import { useEffect, useState } from "react";

import { hasAccessToken } from "../../lib/api/gateway";
import { demoModeEnabled } from "../../lib/api/source";
import { GATEWAY_ROUTES } from "../../lib/api/routes";
import { Label, Panel, Readout, StatusChip } from "../system/primitives";
import { ModelRegistryPanel } from "../models/ModelRegistryPanel";
import { RouteChrome } from "../shell/RouteChrome";

interface Control {
  name: string;
  where: "browser" | "gateway" | "both";
  state: "enforced" | "partial" | "backend";
  detail: string;
}

const CONTROLS: Control[] = [
  {
    name: "Gateway-only egress",
    where: "browser",
    state: "enforced",
    detail:
      "lib/api/gateway.ts is the only module that calls fetch, and it refuses " +
      "absolute URLs — a path arriving in a response body cannot redirect a call.",
  },
  {
    name: "Token storage",
    where: "browser",
    state: "enforced",
    detail:
      "The bearer token is a module-scoped variable. Never localStorage or " +
      "sessionStorage; it dies with the tab, which is why a refresh signs you out.",
  },
  {
    name: "Tenant isolation",
    where: "gateway",
    state: "backend",
    detail:
      "organization_id is never sent by the client. The gateway derives it from " +
      "the verified token, so the browser cannot assert a tenant.",
  },
  {
    name: "GeoJSON validation",
    where: "both",
    state: "enforced",
    detail:
      "lib/geo/validate.ts checks ring closure, coordinate range, " +
      "self-intersection, area bounds and the antimeridian before submit. The " +
      "backend validates again — this layer is usability, not a boundary.",
  },
  {
    name: "Bounded retries",
    where: "browser",
    state: "enforced",
    detail:
      "One timeout, at most two retries, 5xx and transport faults only, with " +
      "backoff. 4xx is never retried.",
  },
  {
    name: "HTML injection",
    where: "browser",
    state: "enforced",
    detail:
      "No dangerouslySetInnerHTML anywhere in the app; all backend strings render " +
      "as text nodes.",
  },
  {
    name: "Rate limiting",
    where: "gateway",
    state: "backend",
    detail: "Enforced at the gateway. The client cannot and does not police itself.",
  },
  {
    name: "Audit logging",
    where: "gateway",
    state: "backend",
    detail:
      "Every call carries X-Trace-Id, generated client-side when absent so a " +
      "request that never reached the backend still has an id to quote.",
  },
  {
    name: "Frontend telemetry",
    where: "browser",
    state: "partial",
    detail:
      "Error boundaries capture and log to the console. There is no telemetry " +
      "sink in the gateway contract yet, so nothing is shipped off-device.",
  },
];

const A11Y: { name: string; detail: string }[] = [
  {
    name: "Keyboard",
    detail:
      "Every control is reachable. Esc exits AOI draw mode and closes the mobile " +
      "drawers; Enter commits a drawn AOI.",
  },
  {
    name: "Focus",
    detail: "Focus is restyled, never removed: 1px signal outline at 2px offset.",
  },
  {
    name: "Colour independence",
    detail:
      "Every state chip carries a glyph as well as a colour, so state survives " +
      "greyscale and colour-blindness.",
  },
  {
    name: "Reduced motion",
    detail:
      "prefers-reduced-motion collapses all transitions to 1ms and freezes the " +
      "globe at t=0 — the same scene, not a different one.",
  },
  {
    name: "Comparison wipe",
    detail:
      "The before/after divider is a real range input, so it works with arrow " +
      "keys and announces its position.",
  },
  {
    name: "Live regions",
    detail:
      "AOI validation and run status are aria-live, so changes are announced " +
      "without moving focus.",
  },
];

const TONE = { enforced: "ok", partial: "warn", backend: "idle" } as const;

export function AdminScreen() {
  const demo = demoModeEnabled();
  const [token, setToken] = useState(false);

  useEffect(() => setToken(hasAccessToken()), []);

  return (
    <RouteChrome title="Admin">
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "20px 20px 60px" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
            gap: 16,
          }}
        >
          <Panel title="Session">
            <div style={{ padding: 10 }}>
              <Readout
                label="Access token"
                value={token ? "Held in memory" : "None"}
                tone={token ? undefined : "dim"}
              />
              <Readout label="Persisted" value="No — by design" />
              <Readout
                label="Organisation"
                value={null}
                reason="Derived from the verified token at the gateway; the browser never sees or sends it."
              />
              <Readout
                label="Role"
                value={null}
                reason="The gateway publishes no identity route; RBAC is enforced server-side per call."
              />
              <Readout label="Environment" value={demo ? "DEMO (fixtures)" : "LIVE"} />
            </div>
          </Panel>

          <Panel title="Gateway routes">
            <div style={{ padding: 10 }}>
              <p className="mono faint" style={{ margin: "0 0 8px", fontSize: 9.5, lineHeight: 1.5 }}>
                The complete set of paths this client may call. Checked against
                docs/openapi/gateway.json by a contract test.
              </p>
              {Object.entries(GATEWAY_ROUTES).map(([name, path]) => (
                <div className="readout" key={name} style={{ minHeight: 17 }}>
                  <Label faint>{name}</Label>
                  <span className="readout-value readout-value-id" style={{ fontSize: 9.5 }}>
                    {path}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div style={{ marginTop: 16 }}>
          <ModelRegistryPanel />
        </div>

        <div style={{ marginTop: 16 }}>
          <Panel title="Security controls">
            <div style={{ padding: 10 }}>
              {CONTROLS.map((c, i) => (
                <div
                  key={c.name}
                  style={{
                    paddingBottom: 8,
                    marginBottom: 8,
                    borderBottom:
                      i === CONTROLS.length - 1 ? "none" : "1px solid var(--hairline)",
                  }}
                >
                  <div className="row" style={{ gap: 8 }}>
                    <span style={{ fontSize: 12.5 }}>{c.name}</span>
                    <div className="band-spacer" />
                    <StatusChip tone="idle">{c.where}</StatusChip>
                    <StatusChip tone={TONE[c.state]}>{c.state}</StatusChip>
                  </div>
                  <p
                    className="mono faint"
                    style={{ margin: "3px 0 0", fontSize: 10, lineHeight: 1.5 }}
                  >
                    {c.detail}
                  </p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div style={{ marginTop: 16 }}>
          <Panel title="Accessibility">
            <div style={{ padding: 10 }}>
              {A11Y.map((a, i) => (
                <div
                  key={a.name}
                  style={{
                    paddingBottom: 8,
                    marginBottom: 8,
                    borderBottom:
                      i === A11Y.length - 1 ? "none" : "1px solid var(--hairline)",
                  }}
                >
                  <Label>{a.name}</Label>
                  <p
                    className="mono faint"
                    style={{ margin: "2px 0 0", fontSize: 10, lineHeight: 1.5 }}
                  >
                    {a.detail}
                  </p>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </RouteChrome>
  );
}
