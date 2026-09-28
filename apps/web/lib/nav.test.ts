/**
 * Route integrity (P5-01).
 *
 * The bug this exists for: the landing page's Console button pointed at a route
 * (/console) that served a superseded screen, while the console the team was
 * building lived at /dashboard and could only be reached by typing it. Nothing
 * failed, because both routes rendered. These tests make that class of drift a
 * failure:
 *
 *   - every declared route is a real page,
 *   - a superseded path is a redirect and never a second implementation,
 *   - no source file links to a path that is neither a page nor a redirect,
 *   - the landing page's Console links go through ROUTES.console.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

import { LEGACY_REDIRECTS, ROUTES, reportRoute } from "./nav";

const WEB_ROOT = join(__dirname, "..");
const APP_DIR = join(WEB_ROOT, "app");

/** True when `path` resolves to an app/**\/page.tsx, honouring [dynamic] segments. */
function pageExists(path: string): boolean {
  const segments = path.split("?")[0]!.split("/").filter(Boolean);
  const walk = (dir: string, rest: string[]): boolean => {
    if (rest.length === 0) return existsSync(join(dir, "page.tsx"));
    const [head, ...tail] = rest;
    const entries = readdirSync(dir).filter((e) => statSync(join(dir, e)).isDirectory());
    const literal = entries.find((e) => e === head);
    if (literal && walk(join(dir, literal), tail)) return true;
    const dynamic = entries.find((e) => /^\[[^\]]+\]$/.test(e));
    return dynamic ? walk(join(dir, dynamic), tail) : false;
  };
  return walk(APP_DIR, segments);
}

/** A redirect destination like /dashboard/reports/:id maps onto [id]. */
const asPage = (destination: string) => destination.replace(/:[A-Za-z]+/g, "x");

function sourceFiles(): { rel: string; text: string }[] {
  const out: { rel: string; text: string }[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      if (entry === "node_modules" || entry.startsWith(".")) continue;
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
        out.push({ rel: relative(WEB_ROOT, full), text: readFileSync(full, "utf8") });
      }
    }
  };
  for (const d of ["app", "components", "lib"]) walk(join(WEB_ROOT, d));
  return out;
}

describe("the route table", () => {
  it.each(Object.entries(ROUTES))("%s -> %s is a real page", (_name, path) => {
    if (path === "/") {
      expect(existsSync(join(APP_DIR, "page.tsx"))).toBe(true);
    } else {
      expect(pageExists(path), `${path} has no app/**/page.tsx`).toBe(true);
    }
  });

  it("makes /dashboard the canonical mission console", () => {
    expect(ROUTES.console).toBe("/dashboard");
  });

  it("encodes the mission id in a report route", () => {
    expect(reportRoute("msn-1")).toBe("/dashboard/reports/msn-1");
    expect(reportRoute("a/b?c")).toBe("/dashboard/reports/a%2Fb%3Fc");
  });
});

describe("superseded routes", () => {
  it.each(LEGACY_REDIRECTS.map((r) => [r.source, r.destination]))(
    "%s redirects to %s and no longer has a page of its own",
    (source, destination) => {
      expect(
        pageExists(asPage(source!)),
        `${source} still has a page — a redirect and a page at one path means ` +
          "two implementations of the same screen",
      ).toBe(false);
      expect(pageExists(asPage(destination!)), `${destination} is not a page`).toBe(true);
    },
  );

  it("sends the old /console straight to the canonical console", () => {
    const r = LEGACY_REDIRECTS.find((x) => x.source === "/console");
    expect(r?.destination).toBe(ROUTES.console);
  });
});

describe("in-app links", () => {
  const LINK = /(?:href=|href:\s*|router\.(?:push|replace)\()\{?\s*["'`](\/[^"'`{$?#]*)/g;

  it("only target pages, never a superseded path", () => {
    const legacy = new Set(LEGACY_REDIRECTS.map((r) => r.source));
    const bad: string[] = [];
    for (const f of sourceFiles()) {
      // nav.ts declares the legacy paths on purpose; the API routes are not pages.
      if (f.rel === "lib/nav.ts" || f.rel.startsWith("lib/api/")) continue;
      for (const m of f.text.matchAll(LINK)) {
        const path = m[1]!.replace(/\/$/, "") || "/";
        if (path === "/" || path.startsWith("/api/") || path.startsWith("/fixtures/")) continue;
        if (path.startsWith("/geo/") || path.startsWith("/sounds/")) continue;
        if (legacy.has(path) || !pageExists(path)) bad.push(`${f.rel}: ${path}`);
      }
    }
    expect(bad, "link to a path that is not a page — use ROUTES from lib/nav").toEqual([]);
  });

  it("send every landing Console link through ROUTES.console", () => {
    for (const file of ["Nav", "Hero", "Closing"]) {
      const text = readFileSync(
        join(WEB_ROOT, `components/landing/sections/${file}.tsx`),
        "utf8",
      );
      expect(text, `${file}.tsx must link the console through ROUTES`).toMatch(
        /ROUTES\.console/,
      );
      expect(text, `${file}.tsx still hard-codes /console`).not.toMatch(
        /["'`]\/console["'`]/,
      );
    }
  });
});
