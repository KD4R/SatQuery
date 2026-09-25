/**
 * Reading a bearer token's claims in the browser, for display only (P5-15).
 *
 * The browser cannot verify a signature and this does not try. It base64url-decodes
 * the payload so an operator can see which token they just pasted. The gateway is
 * the only thing that verifies anything, and a 401 or 403 from a call is the real
 * answer about whether a token is good.
 *
 * Kept out of the component so it can be tested, and out of gateway.ts so that
 * module stays the one place that calls fetch and nothing else.
 */

/** What packages/auth builds an AuthContext from: sub, roles, exp. */
export interface TokenClaims {
  subject: string | null;
  roles: string[];
  expiresAt: Date | null;
}

/**
 * Returns null for anything that is not three dot-separated segments with a
 * decodable JSON middle. That includes opaque reference tokens, which are
 * legitimate -- an unreadable token is not a rejected one, and the caller renders
 * NOT AVAILABLE rather than an error.
 */
export function readClaims(token: string): TokenClaims | null {
  const segments = token.split(".");
  if (segments.length !== 3) return null;

  let payload: unknown;
  try {
    const base64 = segments[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    payload = JSON.parse(
      decodeURIComponent(
        atob(padded)
          .split("")
          .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
          .join(""),
      ),
    );
  } catch {
    return null;
  }

  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) return null;
  const body = payload as Record<string, unknown>;

  return {
    subject: typeof body.sub === "string" ? body.sub : null,
    // Anything non-string in roles is dropped rather than coerced: a token whose
    // roles are malformed should show the roles it actually carries, not "[object
    // Object]" rendered as a role the operator might believe they hold.
    roles: Array.isArray(body.roles) ? body.roles.filter((r): r is string => typeof r === "string") : [],
    // exp is seconds since the epoch (RFC 7519). Milliseconds here would put every
    // token fifty thousand years in the future and never warn about an expired one.
    expiresAt: typeof body.exp === "number" && Number.isFinite(body.exp) ? new Date(body.exp * 1000) : null,
  };
}

/** True when the token says it has expired. A token with no exp has not. */
export function hasExpired(claims: TokenClaims | null, now: number = Date.now()): boolean {
  return claims?.expiresAt ? claims.expiresAt.getTime() < now : false;
}
