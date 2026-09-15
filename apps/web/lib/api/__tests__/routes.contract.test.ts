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

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { ALL_ROUTE_PATHS, buildPath, GATEWAY_ROUTES } from "../routes";

const SPEC = join(__dirname, "../../../../../docs/openapi/gateway.json");

function specPaths(): string[] {
  const doc = JSON.parse(readFileSync(SPEC, "utf8")) as {
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
