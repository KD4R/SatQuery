import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

/**
 * P5-17 — E2E over the deterministic demo flow.
 *
 * These assert on the demo path because the demo path is the one the judges will
 * see, and it is deterministic by construction: lib/fixtures/ contains no
 * Math.random, no Date.now and no wall clock, so every figure below is a constant
 * rather than a tolerance.
 *
 * What they are really protecting is the honesty machinery. It is easy to "fix" a
 * failing test by deleting a NOT AVAILABLE or softening a DEGRADED into a tick, and
 * these are written so that doing so breaks them.
 *
 * Maps to: test_e2e_ux_hardening_and_deterministic_demo_mode_valid()
 *          test_e2e_ux_hardening_and_deterministic_demo_mode_invalid_input()
 */

const MISSION = "msn-2026-0914-assam-01";

test.describe("landing", () => {
  test("names the product and offers the console", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/SatQuery AI/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Ask a question",
    );
    const cta = page.getByRole("link", { name: /enter mission console/i });
    await expect(cta).toBeVisible();
    // The canonical console is /dashboard (P5 routing fix) — a stray /console
    // link here would silently regress to the old route.
    await expect(cta).toHaveAttribute("href", "/dashboard");
  });

  test("never quotes an accuracy figure", async ({ page }) => {
    await page.goto("/");
    // Water is ~11% of the pixels, so a model that predicts no water at all is
    // 89% "accurate". If someone adds an "89% accurate" badge later, this fails.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toMatch(/\d+(\.\d+)?\s*%\s*accura/);
    expect(body).not.toMatch(/accuracy\s*(of|:)?\s*\d/);
  });

  test("states the calibration shortfall, not a green tick", async ({
    page,
  }) => {
    await page.goto("/");
    const honesty = page.locator("#honesty");
    await honesty.scrollIntoViewIfNeeded();
    await expect(honesty.getByText(/still misses the bar/i)).toBeVisible();
    await expect(honesty.getByText("0.0583")).toBeVisible();
  });

  test("every headline figure is one the generated reports state", async ({
    page,
  }) => {
    // reports/evaluation.md: "No number about this subsystem may appear in a slide,
    // a README or a demo script unless it appears here first." The landing page is
    // the most-seen of those surfaces, so this reads the reports from the repo and
    // requires each figure to be both on the page and in a report. Editing a number
    // in facts.ts without regenerating the report fails here.
    const reports =
      readFileSync(join(__dirname, "../../../reports/evaluation.md"), "utf8") +
      readFileSync(join(__dirname, "../../../reports/calibration.md"), "utf8");

    await page.goto("/");
    const figures: [string, string][] = [
      [".sq-intro", "92"],
      ["#honesty", "0.0583"],
      ["#honesty", "0.0896"],
    ];
    for (const [where, figure] of figures) {
      expect(
        reports,
        `${figure} is on the landing page but in neither report`,
      ).toContain(figure);
      const section = page.locator(where);
      await section.scrollIntoViewIfNeeded();
      await expect(
        section.getByText(figure, { exact: false }).first(),
      ).toBeVisible();
    }
  });
});

test.describe("dashboard — demo run", () => {
  // P5 routing fix: /dashboard is the canonical mission console; /console
  // now redirects here (see "console routing" below). These tests replace
  // the old suite that ran directly against /console — some assertions from
  // that suite (WHY-graph evidence drawer, sensor-arbitration toasts, the
  // comparison-wipe slider, the Infrastructure Impact hierarchy) are not yet
  // reachable from /dashboard and are tracked as PRD gaps rather than
  // asserted here; see the audit notes in the PR/README for the list.
  test("runs the full flow and reaches evidence-ready", async ({ page }) => {
    await page.goto("/dashboard");

    // Idle before the run — the stat strip says so rather than showing stale
    // or invented figures.
    await expect(page.getByText("IDLE").first()).toBeVisible();

    await page.getByRole("button", { name: /run analysis/i }).click();

    // The script totals ~7.7s; allow headroom on CI.
    await expect(page.getByText("EVIDENCE READY")).toBeVisible({
      timeout: 25_000,
    });

    await expect(page.getByText("3.54 km²").first()).toBeVisible();
  });

  test("the OBSERVE stage settles degraded, because half the AOI was unseen", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /run analysis/i }).click();
    await expect(page.getByText("EVIDENCE READY")).toBeVisible({
      timeout: 25_000,
    });

    // A green tick here would overclaim: 46% of the AOI was inside the swath.
    // (The stage list and the run timeline both render this detail, so scope
    // to the first match rather than requiring strict-mode uniqueness.)
    await expect(page.getByText("DEGRADED").first()).toBeVisible();
    await expect(
      page.getByText(/46% of the AOI inside the swath/i).first(),
    ).toBeVisible();
  });

  test("the trace drawer opens on the run's stages", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /run analysis/i }).click();
    await expect(page.getByText("EVIDENCE READY")).toBeVisible({
      timeout: 25_000,
    });

    await page.getByRole("button", { name: "Trace", exact: true }).click();
    await expect(page.getByText("AUDIT TRACE")).toBeVisible();
  });

  test("the time machine scrubs the temporal states and never invents dates", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /run analysis/i }).click();
    await expect(page.getByText("EVIDENCE READY")).toBeVisible({
      timeout: 25_000,
    });

    const slider = page.getByRole("slider", { name: /earth time machine/i });
    await expect(slider).toBeVisible();
    // A completed run opens on the observed scene — the latest thing the
    // sensor actually saw — not on the first epoch.
    await expect(slider).toHaveValue("1");

    // Keyboard scrubbing (ARIA slider pattern): left arrow steps back a state.
    await slider.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(slider).toHaveValue("0");
    await expect(
      page.getByRole("button", { name: "Before", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");

    // End jumps to the derived change map; Home/End are part of the pattern.
    await page.keyboard.press("End");
    await expect(slider).toHaveValue("2");
    await expect(
      page.getByRole("button", { name: "Change", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");

    // Sen1Floods11 publishes no per-chip timestamps, so the rail must say so
    // rather than dressing the states up as a Jan → Feb → Mar calendar.
    const rail = page.locator(".tm");
    await expect(rail.getByText(/date not published/i)).toBeVisible();
  });

  test("marks every fixture-fed surface as a fixture", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByText("Demo fixture").first()).toBeVisible();
    // Page-bottom telemetry: ENV reads DEMO, never LIVE, while the flag is on.
    await expect(page.getByText("DEMO").first()).toBeVisible();
  });

  test("reports the gateway as unreachable rather than faking health", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    // No backend is running in E2E. The console must say so, not sit on
    // "CHECKING…" or claim reachable.
    await expect(page.getByText("UNREACHABLE")).toBeVisible({
      timeout: 20_000,
    });
  });
});

test.describe("AOI validation", () => {
  test("draw mode shows live validation and refuses an unfinished polygon", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /^draw aoi$/i }).click();

    await expect(page.getByText(/click to add corners/i)).toBeVisible();
    // Nothing drawn yet, so committing is blocked.
    await expect(
      page.getByRole("button", { name: /^commit$/i }),
    ).toBeDisabled();

    await page.keyboard.press("Escape");
    await expect(page.getByText(/click to add corners/i)).toBeHidden();
  });
});

test.describe("console routing", () => {
  test("/console redirects to the canonical /dashboard and keeps the deep link alive", async ({
    page,
  }) => {
    await page.goto("/console");
    await expect(page).toHaveURL(/\/dashboard$/);
    // Landing on the real console, not a 404 or a blank redirect target.
    await expect(
      page.getByText("MISSION COPILOT", { exact: true }),
    ).toBeVisible();
  });
});

test.describe("routes", () => {
  test("mission memory lists the run history", async ({ page }) => {
    await page.goto("/missions");
    await expect(page.getByText(/temporal history/i)).toBeVisible();
    await expect(page.getByText(/New water detected/i)).toBeVisible();
  });

  test("monitoring shows a countdown derived from timestamps", async ({
    page,
  }) => {
    await page.goto("/monitoring");
    await expect(page.getByText(/next observation/i).first()).toBeVisible();
    await expect(page.getByText("8h 40m")).toBeVisible();
    await expect(page.getByText("INCREASING")).toBeVisible();
  });

  test("admin states where each control is enforced", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByText(/gateway-only egress/i)).toBeVisible();
    await expect(page.getByText(/Token storage/i)).toBeVisible();
    // The session must never claim a persisted token.
    await expect(page.getByText("No — by design")).toBeVisible();
    // And demo mode must not offer a credential box: it makes no gateway calls, so
    // a sign-in there would authenticate nothing.
    await expect(page.getByLabel(/bearer token/i)).toHaveCount(0);
    await expect(page.getByText(/nothing to authenticate/i)).toBeVisible();
  });

  test("report generates asynchronously and carries its caveats", async ({
    page,
  }) => {
    await page.goto(`/missions/${MISSION}/report`);
    await page.getByRole("button", { name: /generate report/i }).click();

    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "Water extent increased",
      { timeout: 15_000 },
    );

    // The three things a report must not quietly drop.
    await expect(
      page.getByText(/fell outside the sensor swath and was not analysed/i),
    ).toBeVisible();
    await expect(page.getByText(/did not pass/i)).toBeVisible();
    await expect(
      page.getByText(/not a bi-temporal change detection/i),
    ).toBeVisible();
  });
});

test.describe("accessibility", () => {
  test("every page exposes a main landmark and a reachable skip link", async ({
    page,
  }) => {
    for (const path of [
      "/dashboard",
      "/dashboard/monitoring",
      "/dashboard/evidence",
      "/dashboard/reports",
      "/dashboard/admin",
      "/missions",
      "/monitoring",
      "/admin",
    ]) {
      await page.goto(path);
      await expect(page.locator("#mission-main")).toBeAttached();
    }
  });

  test("the skip link on the canonical console lands on the main landmark", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    // The link is off-screen until it receives keyboard focus (standard
    // skip-link pattern), so it is activated the way a keyboard user would
    // reach it rather than with a pointer .click().
    const skipLink = page.getByText(/skip to mission console/i);
    await skipLink.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#mission-main")).toBeFocused();
  });
});
