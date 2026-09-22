/**
 * The demo-mode isolation gate (P5-17, and P6-02's no-fabrication rule).
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * CI's `lint` job carries a P6 no-fabrication gate that greps for
 * `demo_?mode|use_?mock|MOCK_|FAKE_|stub_data` across apps/, services/ and
 * packages/, and fails on any hit. P5-17 is a P0 issue titled "E2E UX hardening
 * and deterministic demo mode". As written the two cannot both be satisfied: the
 * gate makes the requirement unimplementable.
 *
 * The gate's intent is right and worth keeping — nothing may fabricate success or
 * serve mock data as real. But a keyword ban cannot tell a service quietly
 * returning invented readings from a frontend demo harness that badges every
 * value it shows. It only checks that a word is absent.
 *
 * So this replaces the word-check with a property-check for apps/web. It asserts
 * the isolation actually holds, which is strictly stronger than asserting the
 * word "demo" does not appear. The gate keeps its full zero-tolerance strength
 * over services/ and packages/, where a demo switch has no legitimate use.
 *
 * Renaming `demoModeEnabled` to something the regex misses would have made CI
 * green in about a minute. That is gate evasion, and this repo has been through
 * that once already (ADR-0007 D16). The honest move is to change the gate in the
 * open and argue for it.
 *
 * @see .github/workflows/ci.yml — "No fabricated data" step
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const WEB_ROOT = join(__dirname, "../..");
const SOURCE_DIRS = ["app", "components", "lib"];

/** The single module permitted to read the demo-mode environment variable. */
const ENV_READER = "lib/api/source.ts";

/**
 * Files allowed to import the fixture barrel. Every one of these renders the
 * fixture badge. Adding a file here is a deliberate act a reviewer will see in
 * the diff — which is the point.
 */
const FIXTURE_CONSUMERS = new Set([
  // Each of these either renders <ProvenanceBadge> itself or is owned by a
  // component that does.
  "components/MissionConsole.tsx",
  "components/mission/MissionMemory.tsx",
  "components/mission/MonitoringScreen.tsx",
  "components/report/ReportScreen.tsx",
  // The demo run's state machine. It has no UI of its own; it feeds the console,
  // which badges. It is listed because it reads DEMO_STAGES.
  "lib/useMissionRun.ts",
]);

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    // Test files are excluded everywhere: this file necessarily contains every
    // pattern it searches for, and so would any test of the fixtures.
    else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

function sourceFiles(): { path: string; rel: string; text: string }[] {
  return SOURCE_DIRS.flatMap((d) => walk(join(WEB_ROOT, d))).map((path) => ({
    path,
    rel: relative(WEB_ROOT, path),
    text: readFileSync(path, "utf8"),
  }));
}

/** Strip comments so prose mentioning the env var is not read as code. */
function code(text: string): string {
  return text
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

describe("demo mode is confined to one switch", () => {
  it("is read in exactly one module", () => {
    const readers = sourceFiles()
      // The *read*, not the name: one screen names the variable in copy that
      // tells the operator how to run the demo, which is not a switch.
      .filter((f) => /process\.env\.NEXT_PUBLIC_DEMO_MODE/.test(code(f.text)))
      .map((f) => f.rel)
      .sort();

    expect(
      readers,
      "Only lib/api/source.ts may read the demo flag. Every other module must " +
        "take `demo` as a prop or call demoModeEnabled(), so there is one place " +
        "to audit and one place to change.",
    ).toEqual([ENV_READER]);
  });
});

describe("fixtures are a boundary, not a library", () => {
  const imports = (text: string) =>
    [...code(text).matchAll(/from\s+"([^"]*fixtures[^"]*)"/g)].map((m) => m[1]!);

  it("are imported only by the declared consumers", () => {
    const offenders = sourceFiles()
      .filter((f) => !f.rel.startsWith("lib/fixtures/"))
      .filter((f) => imports(f.text).length > 0)
      .map((f) => f.rel)
      .filter((rel) => !FIXTURE_CONSUMERS.has(rel))
      .sort();

    expect(
      offenders,
      "A module importing lib/fixtures/ can put unbadged demo data on screen. " +
        "Add it to FIXTURE_CONSUMERS only once the surface it feeds renders " +
        "<ProvenanceBadge>.",
    ).toEqual([]);
  });

  it("are reached only through the barrel, never by deep import", () => {
    const deep: string[] = [];
    for (const f of sourceFiles()) {
      if (f.rel.startsWith("lib/fixtures/")) continue;
      for (const spec of imports(f.text)) {
        // ".../fixtures" is the barrel; ".../fixtures/assam" bypasses it.
        if (!/fixtures$/.test(spec)) deep.push(`${f.rel} → ${spec}`);
      }
    }
    expect(
      deep,
      "Deep imports bypass lib/fixtures/index.ts, which is the one file that " +
        "makes `grep -rn lib/fixtures` a complete list of demo-data entry points.",
    ).toEqual([]);
  });

  it("never reach the API client", () => {
    // If a fixture could call the gateway, or the client could read a fixture,
    // the two sources of truth would be able to blur into each other.
    const leaks = walk(join(WEB_ROOT, "lib/fixtures"))
      .map((p) => ({ rel: relative(WEB_ROOT, p), text: readFileSync(p, "utf8") }))
      .filter((f) => /from\s+"[^"]*api\/(gateway|client)"/.test(code(f.text)))
      .map((f) => f.rel);
    expect(leaks).toEqual([]);
  });
});

describe("fixtures are deterministic", () => {
  /**
   * The demo has to render identically on every run — that is what lets the
   * Playwright suite assert on exact figures instead of tolerances, and what
   * stops a judge seeing different numbers than the rehearsal did.
   */
  const NONDETERMINISM: [RegExp, string][] = [
    [/Math\.random/, "Math.random()"],
    [/Date\.now\s*\(/, "Date.now()"],
    [/new Date\s*\(\s*\)/, "new Date() with no argument"],
    [/performance\.now/, "performance.now()"],
    [/crypto\.randomUUID/, "crypto.randomUUID()"],
  ];

  it.each(NONDETERMINISM)("contain no %s", (pattern, label) => {
    const offenders = walk(join(WEB_ROOT, "lib/fixtures"))
      .map((p) => ({ rel: relative(WEB_ROOT, p), text: code(readFileSync(p, "utf8")) }))
      .filter((f) => pattern.test(f.text))
      .map((f) => f.rel);

    expect(
      offenders,
      `${label} in a fixture makes the demo non-reproducible. Pin the value ` +
        `instead — FIXTURE_EPOCH exists for exactly this.`,
    ).toEqual([]);
  });

  it("stamp every fixture with a pinned timestamp", () => {
    const assam = readFileSync(join(WEB_ROOT, "lib/fixtures/assam.ts"), "utf8");
    expect(assam).toMatch(/export const FIXTURE_EPOCH = "20\d\d-\d\d-\d\dT/);
  });
});

describe("no mock or stub vocabulary anywhere in the app", () => {
  /**
   * These words, unlike "demo", have no legitimate use in this codebase — there
   * is no mocking layer and no stub data. This half of the original P6 gate is
   * kept at full strength.
   */
  it("uses no mock, fake or stub identifiers", () => {
    const pattern = /use_?mock|MOCK_|FAKE_|stub_data/i;
    const offenders = sourceFiles()
      .filter((f) => pattern.test(code(f.text)))
      .map((f) => f.rel);
    expect(offenders).toEqual([]);
  });
});

describe("the boundary is discoverable", () => {
  it("lists every demo-data entry point in one grep", () => {
    // The claim the PR makes: `grep -rn "lib/fixtures" app components` returns
    // the complete set of places demo data can enter the UI. If that stops being
    // true the claim is false, so it is asserted rather than written down.
    const consumers = sourceFiles()
      .filter((f) => !f.rel.startsWith("lib/fixtures/"))
      .filter((f) => /from\s+"[^"]*fixtures"/.test(code(f.text)))
      .map((f) => f.rel)
      .sort();

    expect(new Set(consumers)).toEqual(FIXTURE_CONSUMERS);
  });
});
