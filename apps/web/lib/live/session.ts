/**
 * Getting a bearer token for the live console (audit W1).
 *
 * The gateway requires a verified JWT on every route. A local stack has no
 * identity provider, so the gateway offers POST /api/v1/auth/dev-token, which
 * answers only when it runs with ENVIRONMENT=development and
 * SATQUERY_DEV_LOGIN=1 (404 everywhere else).
 *
 * The token stays in lib/api/gateway's module variable — never in storage — so
 * a reload simply mints a new one. When the route is not available, the console
 * asks the operator to paste a credential on /dashboard/admin instead.
 *
 * The route is deliberately not in GATEWAY_ROUTES: it is excluded from the
 * published OpenAPI document (include_in_schema=False), and the route-contract
 * test compares that table with docs/openapi/gateway.json.
 */

import { GatewayError, hasAccessToken, request, setAccessToken } from "../api/gateway";

export const DEV_TOKEN_PATH = "/api/v1/auth/dev-token";

export type SessionState =
  | { kind: "ready"; via: "existing" | "dev-login"; orgId: string | null }
  | { kind: "needs-credential"; message: string }
  | { kind: "gateway-down"; message: string };

interface DevTokenResponse {
  access_token: string;
  org_id: string;
  roles: string[];
  expires_in: number;
}

let lastOrg: string | null = null;

/** Make sure a token is set; mint a development one when allowed. */
export async function ensureSession(signal?: AbortSignal): Promise<SessionState> {
  if (hasAccessToken()) return { kind: "ready", via: "existing", orgId: lastOrg };
  try {
    const res = await request<DevTokenResponse>(DEV_TOKEN_PATH, {
      method: "POST",
      body: {},
      signal,
      timeoutMs: 6000,
    });
    setAccessToken(res.data.access_token);
    lastOrg = res.data.org_id ?? null;
    return { kind: "ready", via: "dev-login", orgId: lastOrg };
  } catch (caught) {
    if (caught instanceof GatewayError && isGatewayDown(caught)) {
      return { kind: "gateway-down", message: caught.body.message };
    }
    return {
      kind: "needs-credential",
      message:
        "This gateway does not offer development sign-in. Paste a bearer token on the Admin page to run live missions.",
    };
  }
}

/** Drop the token (after a 401) so the next ensureSession mints a fresh one. */
export function dropSession(): void {
  setAccessToken(null);
  lastOrg = null;
}

/**
 * True when the failure means "the gateway is not there" rather than "the
 * gateway said no": refused connection, timeout, or a proxy 5xx (the Next dev
 * rewrite answers 500 when the gateway is down).
 */
export function isGatewayDown(err: GatewayError): boolean {
  // A 5xx that carries the gateway's own envelope (e.g. QUEUE_UNAVAILABLE) is a
  // real answer and is shown as such; only bare proxy errors mean "not there".
  return (
    err.status === 0 ||
    err.body.code === "network_unreachable" ||
    (err.status >= 500 && err.body.code.startsWith("http_"))
  );
}
