/**
 * The only module in the browser bundle that calls fetch (P5-02, P5-15).
 *
 * Everything the UI knows about the network goes through `request()`. That is what
 * makes the security rules checkable rather than aspirational:
 *
 *   - The browser talks to the Gateway and nothing else. Absolute URLs are refused,
 *     so a path smuggled in from a response body cannot redirect a call off-origin.
 *   - The bearer token lives in a module-scoped variable. It is never written to
 *     localStorage or sessionStorage -- the PRD forbids long-lived tokens there, and
 *     a variable dies with the tab.
 *   - organization_id is never sent from the client. It is derived server-side from
 *     the verified token (PRD section 5).
 *   - Every call is bounded: one timeout, at most two retries, only for transport
 *     faults and 5xx, with backoff. No retry storms (PRD section 5).
 *   - Failures surface as ErrorResponse carrying trace_id. Nothing is swallowed and
 *     nothing silently degrades to a fixture -- falling back quietly would be
 *     fabricating success, which the PRD prohibits.
 */

import type { ErrorResponse } from "./types";

const BASE = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "/api/v1";

const DEFAULT_TIMEOUT_MS = 15_000;
const MAX_ATTEMPTS = 3; // the first try plus two retries
const BACKOFF_MS = [250, 750];

/** In-memory only. Never persisted. Cleared on reload, which is the point. */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

/**
 * Build a WebSocket URL for a given path, converting http(s) to ws(s).
 * Uses NEXT_PUBLIC_API_URL for the host so the WS connects to the same
 * origin as the REST calls.
 */
export function buildWsUrl(path: string): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "";
  if (apiUrl) {
    const base = apiUrl.replace(/^http/, "ws").replace(/\/$/, "");
    return `${base}${path}`;
  }
  // Fallback: use same-origin with ws/wss
  const proto = typeof window !== "undefined" && window.location.protocol === "https:" ? "wss" : "ws";
  const host = typeof window !== "undefined" ? window.location.host : "localhost:8000";
  return `${proto}://${host}${path}`;
}

/** Thrown by every failed call. Carries the canonical envelope for the UI. */
export class GatewayError extends Error {
  readonly status: number;
  readonly body: ErrorResponse;

  constructor(status: number, body: ErrorResponse) {
    super(body.message);
    this.name = "GatewayError";
    this.status = status;
    this.body = body;
  }

  get traceId(): string | null {
    return this.body.trace_id ?? null;
  }

  /** True for the states the UI offers a RETRY button on. */
  get retryable(): boolean {
    return this.status === 0 || this.status === 408 || this.status >= 500;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
  /** Set for duplicate-sensitive writes (PRD section 5: Idempotency-Key). */
  idempotencyKey?: string;
  /** Correlation id to propagate. One is generated when absent. */
  traceId?: string;
}

/**
 * Trace ids are generated client-side when the caller has none so that a request
 * which never reaches the backend still has something to show the operator in the
 * failure state. crypto.randomUUID is not in every target, hence the fallback.
 */
export function newTraceId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  const bytes = new Uint8Array(16);
  if (c && typeof c.getRandomValues === "function") c.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function isRelative(path: string): boolean {
  return path.startsWith("/") && !path.startsWith("//");
}

async function readError(
  response: Response,
  fallbackTraceId: string,
): Promise<ErrorResponse> {
  let parsed: unknown = null;
  try {
    parsed = await response.json();
  } catch {
    /* a non-JSON body is normal for 502/504 from a proxy */
  }

  if (parsed && typeof parsed === "object") {
    const record = parsed as Record<string, unknown>;
    // FastAPI validation errors arrive as {detail: [...]}, which is not our envelope.
    if (Array.isArray(record.detail)) {
      return {
        code: "validation_error",
        message: "The gateway rejected the request as invalid.",
        details: record.detail,
        trace_id: fallbackTraceId,
      };
    }
    if (typeof record.code === "string" && typeof record.message === "string") {
      return {
        code: record.code,
        message: record.message,
        details: Array.isArray(record.details) ? record.details : [],
        trace_id:
          typeof record.trace_id === "string" ? record.trace_id : fallbackTraceId,
      };
    }
  }

  return {
    code: `http_${response.status}`,
    message: response.statusText || `Request failed with status ${response.status}.`,
    details: [],
    trace_id: fallbackTraceId,
  };
}

export interface GatewayResult<T> {
  data: T;
  traceId: string;
  status: number;
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<GatewayResult<T>> {
  if (!isRelative(path)) {
    // Refusing absolute URLs is the SSRF guard: a path that arrived in a response
    // body cannot be turned into a call to another host.
    throw new GatewayError(0, {
      code: "invalid_target",
      message: "The client may only call gateway-relative paths.",
      details: [path],
      trace_id: null,
    });
  }

  const method = options.method ?? "GET";
  const traceId = options.traceId ?? newTraceId();
  const url = `${BASE.replace(/\/$/, "")}${path.replace(/^\/api\/v1/, "")}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Trace-Id": traceId,
  };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let lastError: GatewayError | null = null;

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const timeout = new AbortController();
    const timer = setTimeout(
      () => timeout.abort(),
      options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
    );

    // The caller's signal and our timeout both have to be able to cancel.
    const onCallerAbort = () => timeout.abort();
    options.signal?.addEventListener("abort", onCallerAbort);

    try {
      const response = await fetch(url, {
        method,
        headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: timeout.signal,
        credentials: "omit",
        cache: "no-store",
      });

      if (response.ok) {
        const traceHeader = response.headers.get("X-Trace-Id");
        const data =
          response.status === 204 ? (undefined as T) : ((await response.json()) as T);
        return { data, traceId: traceHeader ?? traceId, status: response.status };
      }

      const body = await readError(response, traceId);
      lastError = new GatewayError(response.status, body);

      // 4xx is the caller's fault; repeating it just wastes the operator's time.
      if (response.status < 500) throw lastError;
    } catch (caught) {
      if (caught instanceof GatewayError) {
        lastError = caught;
        if (!caught.retryable) throw caught;
      } else {
        const aborted = options.signal?.aborted === true;
        lastError = new GatewayError(aborted ? 499 : 0, {
          code: aborted ? "cancelled" : "network_unreachable",
          message: aborted
            ? "The request was cancelled."
            : "The gateway could not be reached.",
          details: [],
          trace_id: traceId,
        });
        if (aborted) throw lastError;
      }
    } finally {
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", onCallerAbort);
    }

    const backoff = BACKOFF_MS[attempt];
    if (attempt < MAX_ATTEMPTS - 1 && backoff !== undefined) {
      await new Promise((resolve) => setTimeout(resolve, backoff));
    }
  }

  throw (
    lastError ??
    new GatewayError(0, {
      code: "unknown",
      message: "The request failed for an unknown reason.",
      details: [],
      trace_id: traceId,
    })
  );
}
