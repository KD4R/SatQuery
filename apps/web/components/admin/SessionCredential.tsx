"use client";

/**
 * Supplying the bearer token the console runs live with (P5-15).
 *
 * WHY THIS IS A PASTE BOX AND NOT A SIGN-IN FORM
 *
 * There is no sign-in. packages/auth *verifies* tokens -- RS256 against an OIDC
 * provider's JWKS in production, HS256 in tests -- and no service in this repo
 * mints one. There is no /auth/login, no /token, no identity route on the gateway;
 * `grep -rn "def.*login\|token_endpoint" services/` returns nothing. The platform
 * was built to sit behind someone else's identity provider, and that provider is
 * not part of this project.
 *
 * So the console has exactly two honest options: refuse to run live at all, or let
 * an operator paste a token their identity provider issued. A third option --
 * minting a token in the browser -- would mean shipping the signing secret to
 * every client, which is not a login, it is a public key to the whole API.
 *
 * This is the second option, labelled as what it is. When P1 adds the OIDC
 * redirect, this panel is deleted and setAccessToken() is called from the
 * callback instead; nothing else in the client changes.
 *
 * The claims shown are read from the token's payload WITHOUT verifying its
 * signature -- the browser cannot verify anything, and pretending otherwise would
 * be the same fabrication this console exists to avoid. They are there to answer
 * "which token did I just paste", not "is this token valid". The gateway decides
 * that, and a 401 or 403 from it is the real answer.
 */

import { useState } from "react";

import type { TokenClaims } from "../../lib/api/claims";
import { hasExpired, readClaims } from "../../lib/api/claims";
import { hasAccessToken, setAccessToken } from "../../lib/api/gateway";
import { Label, NotAvailable, Readout, StatusChip } from "../system/primitives";

export function SessionCredential({ onChange }: { onChange: () => void }) {
  const [draft, setDraft] = useState("");
  const [claims, setClaims] = useState<TokenClaims | null>(null);
  const [held, setHeld] = useState(hasAccessToken());

  function apply() {
    const token = draft.trim();
    if (!token) return;
    setAccessToken(token);
    setClaims(readClaims(token));
    setHeld(true);
    setDraft("");
    onChange();
  }

  function clear() {
    setAccessToken(null);
    setClaims(null);
    setHeld(false);
    onChange();
  }

  const expired = hasExpired(claims);

  return (
    <div style={{ borderTop: "1px solid var(--hairline)", marginTop: 8, paddingTop: 8 }}>
      <div className="row" style={{ gap: 8, marginBottom: 6 }}>
        <Label faint>Credential</Label>
        <div className="band-spacer" />
        <StatusChip tone={held ? "ok" : "idle"}>{held ? "Token held" : "No token"}</StatusChip>
      </div>

      <p className="mono faint" style={{ margin: "0 0 8px", fontSize: 9.5, lineHeight: 1.55 }}>
        This platform has no sign-in route — packages/auth verifies tokens issued by
        an external OIDC provider and no service here mints one. Paste a token from
        your provider to run live. It is held in memory only and dies with the tab.
      </p>

      {held ? (
        <>
          <Readout label="Subject" value={claims?.subject ?? null} reason="Opaque token — no readable claims." />
          <Readout
            label="Roles in token"
            value={claims?.roles.length ? claims.roles.join(", ") : null}
            reason="Opaque token — no readable claims."
          />
          <Readout
            label="Expires"
            value={claims?.expiresAt ? claims.expiresAt.toISOString().replace("T", " ").slice(0, 19) + "Z" : null}
            reason="Opaque token — no readable claims."
            tone={expired ? "amber" : undefined}
          />
          {claims ? (
            <p className="mono faint" style={{ margin: "4px 0 0", fontSize: 9.5, lineHeight: 1.5 }}>
              Read from the token body without checking its signature. The gateway is
              what verifies it; a 401 or 403 from a call is the real answer.
            </p>
          ) : null}
          {expired ? (
            <p className="mono amb" style={{ margin: "4px 0 0", fontSize: 10, lineHeight: 1.45 }}>
              ▲ This token&rsquo;s exp is in the past. The gateway will refuse it.
            </p>
          ) : null}
          <button className="btn" style={{ marginTop: 8 }} onClick={clear}>
            Clear token
          </button>
        </>
      ) : (
        <>
          <label className="label faint" htmlFor="access-token">
            Bearer token
          </label>
          <input
            id="access-token"
            className="field"
            type="password"
            autoComplete="off"
            spellCheck={false}
            value={draft}
            placeholder="eyJhbGciOi…"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") apply();
            }}
            style={{ width: "100%", marginTop: 4 }}
          />
          <button
            className="btn btn-primary"
            style={{ marginTop: 8 }}
            disabled={draft.trim() === ""}
            onClick={apply}
          >
            Use token
          </button>
        </>
      )}
    </div>
  );
}

/** Exported for the case where live mode is off and there is nothing to hold. */
export function CredentialUnavailable() {
  return (
    <div style={{ borderTop: "1px solid var(--hairline)", marginTop: 8, paddingTop: 8 }}>
      <Label faint>Credential</Label>
      <div style={{ marginTop: 4 }}>
        <NotAvailable reason="Demo mode makes no gateway calls, so there is nothing to authenticate." />
      </div>
    </div>
  );
}
