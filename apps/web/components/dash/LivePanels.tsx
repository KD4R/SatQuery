"use client";

/**
 * Live-mode result surfaces (audit F2, F3, W3, W6, W7, W10).
 *
 *   ResultCard        the answer at the top of the rail: area, confidence basis,
 *                     scene, sensor, method.
 *   FailureCard       why a run failed and what to try next, per failure kind.
 *   RunningCard       a quiet skeleton while the agent works (no fake progress).
 *   IdleCard          what to do before the first run.
 *   LiveIntelligence  the detail under the map: WHY, confidence, evidence chain,
 *                     what was searched, caveats.
 *
 * Every value comes from lib/live/result.ts, which reads only what the agent
 * published. Missing values print "—" with the reason in a tooltip; nothing is
 * defaulted into a plausible number.
 */

import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  KeyRound,
  Layers,
  RefreshCw,
  Satellite,
  ScrollText,
  WifiOff,
} from "lucide-react";

import { formatUTC } from "../../lib/geo/format";
import { km2ToHa, type LiveResult } from "../../lib/live/result";
import type { FailureKind } from "../../lib/useMissionRun";
import type { ExtentState } from "../../lib/live/useAnalysisExtent";
import type { StepView } from "../../lib/live/steps";
import { ROUTES } from "../../lib/nav";

const NA = "—";

function fmtNum(v: number | null, digits = 2): string {
  return v === null ? NA : v.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function sensorName(code: string | null): string {
  if (!code) return NA;
  if (code === "S1_SAR") return "Sentinel-1 SAR";
  if (code === "S2_OPTICAL") return "Sentinel-2 optical";
  return code;
}

function basisLabel(r: LiveResult): { text: string; tone: "ok" | "warn" } {
  if (r.confidence.modelConfidence === null) {
    return { text: "Model not calibrated", tone: "warn" };
  }
  return { text: `Model ${fmtNum(r.confidence.modelConfidence)}`, tone: "ok" };
}

/* ── Result card ────────────────────────────────────────────────────────── */

export function ResultCard({
  result,
  extent,
  onTrace,
}: {
  result: LiveResult;
  extent: ExtentState;
  onTrace: () => void;
}) {
  const km2 = result.areaKm2;
  const basis = basisLabel(result);
  const degraded = Boolean(result.inference.degradedFrom);
  return (
    <section className="sqd-card sqd-result" aria-label="Result" aria-live="polite">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">
          <CheckCircle2 size={13} /> Result
        </span>
        <span className={`sqd-chip ${degraded ? "is-warn" : "is-ok"}`}>
          {degraded ? "Baseline method" : "Model"}
        </span>
      </header>

      <div className="sqd-figure">
        <b>{km2 === null ? NA : fmtNum(km2)}</b>
        <span>km² of surface water</span>
      </div>
      <p className="sqd-figure-sub">
        {km2 === null ? "No area was reported." : `${fmtNum(km2ToHa(km2), 1)} ha inside the AOI on the acquisition date.`}
      </p>

      <dl className="sqd-facts">
        <div>
          <dt>Confidence</dt>
          <dd>
            {fmtNum(result.confidence.score)}
            <span className={`sqd-chip is-${basis.tone}`} title="How the score was formed">
              {basis.text}
            </span>
          </dd>
        </div>
        <div>
          <dt>Scene date</dt>
          <dd>{formatUTC(result.scene.acquiredAt)}</dd>
        </div>
        <div>
          <dt>Sensor</dt>
          <dd>{sensorName(result.scene.sensor)}</dd>
        </div>
        <div>
          <dt>Scene</dt>
          <dd className="sqd-mono" title={result.scene.id ?? undefined}>
            {result.scene.id ?? NA}
          </dd>
        </div>
        <div>
          <dt>On the map</dt>
          <dd>
            {extent.status === "ready"
              ? `${extent.features} water polygon${extent.features === 1 ? "" : "s"}`
              : extent.status === "loading"
                ? "Loading outline…"
                : extent.status === "unavailable"
                  ? <span title={extent.message}>Outline unavailable</span>
                  : NA}
          </dd>
        </div>
      </dl>

      {result.scene.coverage !== null && result.scene.coverage < 0.98 ? (
        <p className="sqd-note is-warn">
          <AlertTriangle size={12} /> The scene covers about {Math.round(result.scene.coverage * 100)}% of the
          AOI; the rest was not observed.
        </p>
      ) : null}

      <div className="sqd-actions">
        <button className="sqd-btn" type="button" onClick={onTrace}>
          <ScrollText size={13} /> Open trace
        </button>
        <a className="sqd-btn" href="#live-intel">
          <Layers size={13} /> Why &amp; evidence
        </a>
      </div>
    </section>
  );
}

/* ── Failure card ───────────────────────────────────────────────────────── */

const FAILURE_TITLE: Record<FailureKind, string> = {
  agent: "The run finished without a result",
  "gateway-down": "Gateway unreachable",
  auth: "Sign-in needed",
  timeout: "The run took too long",
  request: "The gateway refused the request",
};

export function FailureCard({
  kind,
  message,
  reason,
  hint,
  traceId,
  onRetry,
  onTrace,
}: {
  kind: FailureKind;
  message: string;
  reason: string | null;
  hint: string;
  traceId: string | null;
  onRetry: () => void;
  onTrace: () => void;
}) {
  const Icon = kind === "gateway-down" ? WifiOff : kind === "auth" ? KeyRound : kind === "timeout" ? Clock : AlertTriangle;
  return (
    <section className="sqd-card sqd-failure" role="alert" aria-label="Run failed">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow is-danger">
          <Icon size={13} /> {FAILURE_TITLE[kind]}
        </span>
        {reason ? <span className="sqd-chip is-danger sqd-mono">{reason}</span> : null}
      </header>
      <p className="sqd-failure-msg">
        {kind === "gateway-down"
          ? `The console could not reach the SatQuery gateway${message ? ` (${message})` : ""}.`
          : message}
      </p>
      <p className="sqd-failure-hint">
        <b>Try:</b>{" "}
        {kind === "gateway-down"
          ? "start the backend (docker compose up) and retry."
          : kind === "auth"
            ? "open Admin and paste a bearer token, or enable development sign-in on the gateway."
            : kind === "timeout"
              ? "retry, or check the agent and inference service logs."
              : hint}
      </p>
      <div className="sqd-actions">
        <button className="sqd-btn is-primary" type="button" onClick={onRetry}>
          <RefreshCw size={13} /> Retry
        </button>
        {kind === "auth" ? (
          <Link className="sqd-btn" href={ROUTES.admin}>
            <KeyRound size={13} /> Connect a credential
          </Link>
        ) : null}
        {kind === "agent" ? (
          <button className="sqd-btn" type="button" onClick={onTrace}>
            <ScrollText size={13} /> Open trace
          </button>
        ) : null}
      </div>
      {traceId ? <p className="sqd-trace sqd-mono">trace {traceId}</p> : null}
    </section>
  );
}

/* ── Running / idle ─────────────────────────────────────────────────────── */

export function RunningCard({ current }: { current: StepView | null }) {
  return (
    <section className="sqd-card sqd-running" aria-label="Run in progress" aria-busy="true">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">
          <Satellite size={13} /> Working
        </span>
      </header>
      <p className="sqd-running-step">{current ? `${current.label}…` : "Starting…"}</p>
      <p className="sqd-running-detail">{current?.detail ?? "Sending the request to the gateway."}</p>
      <div className="sqd-skel" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
    </section>
  );
}

export function IdleCard({ aoiReady }: { aoiReady: boolean }) {
  return (
    <section className="sqd-card sqd-idle" aria-label="No analysis yet">
      <header className="sqd-card-head">
        <span className="sqd-eyebrow">No analysis yet</span>
      </header>
      <ol className="sqd-idle-steps">
        <li className={aoiReady ? "is-done" : ""}>
          {aoiReady ? "AOI drawn." : "Search a place, then draw an area on the map (polygon or rectangle)."}
        </li>
        <li>Optionally set a date range; empty means the last 90 days, widened to a year if needed.</li>
        <li>Run. The answer, its confidence and the water outline appear here and on the map.</li>
      </ol>
    </section>
  );
}

/* ── Detail under the map ───────────────────────────────────────────────── */

export function LiveIntelligence({ result }: { result: LiveResult }) {
  const s = result.search;
  return (
    <div className="sqd-intel" id="live-intel">
      <section className="sqd-card sqd-span-2" aria-label="Answer">
        <header className="sqd-card-head">
          <span className="sqd-eyebrow">Answer</span>
          <span className="sqd-chip">{result.citations} evidence citations</span>
        </header>
        <p className="sqd-prose">{result.summary ?? "The agent published no summary for this run."}</p>
      </section>

      <section className="sqd-card" aria-label="Why">
        <header className="sqd-card-head">
          <span className="sqd-eyebrow">Why</span>
        </header>
        {result.why.length === 0 ? (
          <p className="sqd-muted">No explanation was published.</p>
        ) : (
          <dl className="sqd-why">
            {result.why.map((w) => (
              <div key={w.key}>
                <dt>{w.title}</dt>
                <dd>{w.text}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section className="sqd-card" aria-label="Confidence">
        <header className="sqd-card-head">
          <span className="sqd-eyebrow">Confidence</span>
          {result.confidence.passedGate === null ? null : (
            <span className={`sqd-chip ${result.confidence.passedGate ? "is-ok" : "is-warn"}`}>
              {result.confidence.passedGate ? "Passed gate" : "Below gate"}
            </span>
          )}
        </header>
        <dl className="sqd-facts">
          <div>
            <dt>Gate score</dt>
            <dd>{fmtNum(result.confidence.score)}</dd>
          </div>
          <div>
            <dt>Model confidence</dt>
            <dd title={result.confidence.modelBasis ?? undefined}>
              {result.confidence.modelConfidence === null
                ? "Not calibrated"
                : `${fmtNum(result.confidence.modelConfidence)} (${result.confidence.modelBasis ?? "reported"})`}
            </dd>
          </div>
          <div>
            <dt>Score based on</dt>
            <dd>
              {result.confidence.scoreBasis === "acquisition_quality_only"
                ? "Acquisition quality only"
                : result.confidence.scoreBasis === "acquisition_quality_and_model"
                  ? "Acquisition quality and model"
                  : NA}
            </dd>
          </div>
          <div>
            <dt>Pixel size</dt>
            <dd>{result.confidence.resolutionM === null ? NA : `${result.confidence.resolutionM} m`}</dd>
          </div>
          <div>
            <dt>Time from requested period</dt>
            <dd>
              {result.confidence.lagDays === null
                ? NA
                : result.confidence.lagDays === 0
                  ? "Inside the window"
                  : `${result.confidence.lagDays} days`}
            </dd>
          </div>
        </dl>
        {result.uncertainty.length ? (
          <ul className="sqd-list">
            {result.uncertainty.map((u) => (
              <li key={u}>{u}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="sqd-card" aria-label="Evidence chain">
        <header className="sqd-card-head">
          <span className="sqd-eyebrow">Evidence chain</span>
        </header>
        {result.evidence.length === 0 ? (
          <p className="sqd-muted">No evidence graph was published.</p>
        ) : (
          <ol className="sqd-evidence">
            {result.evidence.map((e) => (
              <li key={e.id}>
                <span className="sqd-chip sqd-mono">{e.type.toLowerCase()}</span>
                <div>
                  <b>{e.title}</b>
                  <small>{e.detail || e.source}</small>
                </div>
                <span className="sqd-mono sqd-ev-conf" title="Producer-reported confidence">
                  {e.type === "INFERENCE" || e.type === "METRIC"
                    ? e.confidence === null
                      ? "not calibrated"
                      : fmtNum(e.confidence)
                    : ""}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="sqd-card" aria-label="What was searched">
        <header className="sqd-card-head">
          <span className="sqd-eyebrow">What was searched</span>
        </header>
        {!s ? (
          <p className="sqd-muted">The run did not publish its search parameters.</p>
        ) : (
          <dl className="sqd-facts">
            <div>
              <dt>Area (bbox)</dt>
              <dd className="sqd-mono">{s.bbox ? s.bbox.map((v) => v.toFixed(3)).join(", ") : NA}</dd>
            </div>
            <div>
              <dt>Requested dates</dt>
              <dd>
                {s.requestedWindow
                  ? `${s.requestedWindow.start.slice(0, 10)} → ${s.requestedWindow.end.slice(0, 10)}`
                  : "Not set (automatic)"}
              </dd>
            </div>
            {s.attempts.map((a, i) => (
              <div key={`${a.start}-${i}`}>
                <dt>Search {i + 1}</dt>
                <dd>
                  {a.start.slice(0, 10)} → {a.end.slice(0, 10)} · {a.error ? `error: ${a.error}` : `${a.results} scene(s)`}
                </dd>
              </div>
            ))}
            {s.widened ? (
              <div>
                <dt>Note</dt>
                <dd>Nothing in the last 90 days, so the search was widened to a year.</dd>
              </div>
            ) : null}
            <div>
              <dt>Inference trace</dt>
              <dd className="sqd-mono">{result.inference.traceId ?? NA}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className="sqd-card sqd-span-2" aria-label="Method caveats">
        <header className="sqd-card-head">
          <span className="sqd-eyebrow">Method caveats</span>
          <span className="sqd-chip">{result.inference.producedBy ?? NA}</span>
        </header>
        {result.caveats.length === 0 ? (
          <p className="sqd-muted">No caveats were published.</p>
        ) : (
          <ul className="sqd-list">
            {result.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
