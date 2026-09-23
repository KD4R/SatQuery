/**
 * P5-02 contract test: test_p5_02_schema_compatibility()
 *
 * Asserts that the route table the browser is built against and the gateway's own
 * OpenAPI document describe the same set of paths. This is the check that replaces
 * codegen while the gateway's bodies are untyped -- see ../README.md.
 *
 * It reads gateway.json from the repo rather than a copied fixture, so a route
 * added by P1 that nobody told P5 about fails here.
 */

import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";

import { ALL_ROUTE_PATHS, buildPath, GATEWAY_ROUTES } from "../routes";

/**
 * Walk up for the repo root rather than counting "../" five times. A hard-coded
 * depth breaks silently the moment the file moves, and the ENOENT it throws names
 * a path like "/docs/openapi/gateway.json", which tells you nothing.
 */
function findSpec(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i++) {
    const candidate = join(dir, "docs/openapi/gateway.json");
    if (existsSync(candidate)) return candidate;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error(
    `docs/openapi/gateway.json not found above ${__dirname}. This test reads the ` +
      `gateway spec from the repo, so it must run from inside a checkout.`,
  );
}

function specPaths(): string[] {
  const doc = JSON.parse(readFileSync(findSpec(), "utf8")) as {
    paths: Record<string, unknown>;
  };
  return Object.keys(doc.paths).sort();
}

describe("gateway route table", () => {
  it("declares every path the gateway publishes", () => {
    const missing = specPaths().filter((p) => !ALL_ROUTE_PATHS.includes(p));
    expect(
      missing,
      `gateway.json publishes routes the client does not declare. Add them to ` +
        `routes.ts (and a typed call in client.ts) or the UI cannot reach them.`,
    ).toEqual([]);
  });

  it("declares no path the gateway does not publish", () => {
    const published = specPaths();
    const invented = [...ALL_ROUTE_PATHS].filter((p) => !published.includes(p));
    expect(
      invented,
      `routes.ts declares paths absent from gateway.json. Calling one would 404 at ` +
        `runtime; the gateway is the only surface the browser may call.`,
    ).toEqual([]);
  });

  it("has no duplicate paths", () => {
    expect(new Set(ALL_ROUTE_PATHS).size).toBe(ALL_ROUTE_PATHS.length);
  });
});

describe("buildPath", () => {
  it("substitutes and percent-encodes parameters", () => {
    expect(buildPath(GATEWAY_ROUTES.job, { job_id: "a/b" })).toBe(
      "/api/v1/jobs/a%2Fb",
    );
  });

  it("refuses to build a path with a missing parameter", () => {
    // Silently leaving "{mission_id}" in the URL would produce a confusing 404.
    expect(() => buildPath(GATEWAY_ROUTES.mission, {})).toThrow(/mission_id/);
  });
});
