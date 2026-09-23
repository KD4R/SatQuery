import { describe, expect, it } from "vitest";

import { hasExpired, readClaims } from "./claims";

/** Build a JWT-shaped string. The signature is never read, so it is a placeholder. */
function jwt(payload: unknown): string {
  const encode = (value: unknown) =>
    Buffer.from(JSON.stringify(value))
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${encode({ alg: "RS256", typ: "JWT" })}.${encode(payload)}.not-checked`;
}

describe("readClaims", () => {
  it("reads sub, roles and exp", () => {
    const claims = readClaims(
      jwt({ sub: "user@satquery.test", roles: ["analyst"], exp: 1_800_000_000 }),
    );
    expect(claims).toEqual({
      subject: "user@satquery.test",
      roles: ["analyst"],
      expiresAt: new Date(1_800_000_000_000),
    });
  });

  it("treats exp as seconds, not milliseconds", () => {
    // The whole point of showing exp is warning about an expired token. Reading
    // seconds as milliseconds puts every token in 1970 and warns about all of them;
    // the reverse puts them in the year 58000 and warns about none.
    const claims = readClaims(jwt({ exp: 1_800_000_000 }));
    expect(claims?.expiresAt?.getUTCFullYear()).toBe(2027);
  });

  it("returns null for an opaque token rather than throwing", () => {
    for (const opaque of ["", "abc", "a.b", "a.b.c.d", "not-base64!.also-not!.x"]) {
      expect(readClaims(opaque)).toBeNull();
    }
  });

  it("returns null when the payload is not a JSON object", () => {
    expect(readClaims(jwt("a string"))).toBeNull();
    expect(readClaims(jwt([1, 2, 3]))).toBeNull();
  });

  it("drops non-string roles instead of coercing them", () => {
    // "[object Object]" rendered next to "Roles in token" would read as a role the
    // operator holds. It is not one.
    expect(readClaims(jwt({ roles: ["analyst", 7, { admin: true }, null] }))?.roles).toEqual([
      "analyst",
    ]);
  });

  it("reports absent claims as null, not as empty strings", () => {
    const claims = readClaims(jwt({}));
    expect(claims).toEqual({ subject: null, roles: [], expiresAt: null });
  });

  it("decodes non-ASCII subjects", () => {
    expect(readClaims(jwt({ sub: "प्रयोक्ता@satquery.test" }))?.subject).toBe(
      "प्रयोक्ता@satquery.test",
    );
  });
});

describe("hasExpired", () => {
  const now = Date.UTC(2026, 8, 23);

  it("is true only once exp has passed", () => {
    expect(hasExpired(readClaims(jwt({ exp: now / 1000 - 1 })), now)).toBe(true);
    expect(hasExpired(readClaims(jwt({ exp: now / 1000 + 1 })), now)).toBe(false);
  });

  it("does not claim an expiry the token never stated", () => {
    expect(hasExpired(readClaims(jwt({})), now)).toBe(false);
    expect(hasExpired(null, now)).toBe(false);
  });
});
