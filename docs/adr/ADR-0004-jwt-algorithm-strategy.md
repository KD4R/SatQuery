# ADR-0004: JWT Algorithm Strategy — HS256 (Dev) / RS256 (Production)

**Status:** Accepted  
**Date:** 2026-09-11  
**Deciders:** Platform Engineering Team, Security Lead  

---

## Context

JWT verification strategy needs to balance:
- **Security**: Production tokens must be verifiable without exposing a shared secret.
- **Developer ergonomics**: Running tests locally must not require a live OIDC provider.
- **CI pipeline**: Automated tests must work with no external network dependencies.

## Decision

We support **two algorithms**, selected at runtime via the `AUTH_ALGORITHM` environment variable:

| Environment | Algorithm | Key Material |
|---|---|---|
| Production | `RS256` | Public key fetched from `AUTH_JWKS_URL` (OIDC JWKS endpoint) |
| Dev / CI / Test | `HS256` | `AUTH_SECRET_KEY` environment variable |

### Key Security Controls

1. **Algorithm pinning**: The server-side `AUTH_ALGORITHM` config drives which algorithm is used for verification. The `alg` header from the incoming token is inspected only as a hint — if it conflicts with the server config it is rejected.
2. **HS256 is blocked in production**: The `decode_and_verify()` function in `packages/auth/jwt.py` will not use HS256 if `AUTH_ALGORITHM=RS256` is configured, even if the token header claims `HS256`. This prevents the **algorithm confusion attack** (CVE pattern: attacker signs a token with the public key using HS256, claiming it as HS256-signed).
3. **Claim validation**: `exp`, `iat`, `iss`, `aud` are all validated. `sub` and `org_id` are required claims — absence raises `TokenMissingClaimError`.

## OWASP Alignment

- **A02 Cryptographic Failures**: RS256 with asymmetric keys ensures the signing key never leaves the identity provider. HS256 is explicitly disabled for production deployments.
- **A07 Identification and Authentication Failures**: Algorithm confusion is mitigated by server-side algorithm pinning. Short-lived tokens (15 min default) limit blast radius of a compromised token.

## Consequences

### Positive
- Zero OIDC dependency in CI — tests run completely offline.
- RS256 in prod means no shared secret that could leak from a compromised service.
- The dual-algorithm pattern is well-understood and widely documented (Auth0, Okta patterns).

### Negative / Mitigations
- Developers must remember to set `AUTH_ALGORITHM=HS256` locally. Mitigated by `conftest.py` auto-setting this for all test runs.
- JWKS endpoint adds a network call per service startup (key fetch). Mitigated by caching the public key after first fetch.

## Alternatives Considered

| Option | Reason Rejected |
|---|---|
| HS256 everywhere | Shared secret must be distributed to every service — catastrophic if one service is compromised |
| RS256 everywhere (including tests) | Requires running a local OIDC provider in CI — too much friction for P1 |
| Opaque tokens + introspection | Adds per-request network latency to the auth provider; stateless JWT is preferred |
