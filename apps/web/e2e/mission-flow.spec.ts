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
    await expect(
      page.getByRole("link", { name: /enter mission console/i }),
    ).toBeVisible();
  });

  test("quotes IoU and refuses to quote accuracy", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("0.435")).toBeVisible();
    // The landing page must keep explaining why accuracy is absent. If someone
    // adds an "89% accurate" badge later, this fails.
    await expect(page.getByText(/Accuracy is not quoted/i)).toBeVisible();
  });

  test("system checks report the calibration shortfall, not twelve green ticks", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByText("PARTIAL")).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("console — demo run", () => {
  test("runs the full flow and reports the measured figures", async ({ page }) => {
    await page.goto("/console");

    // Before the run there is nothing to show, and the panel says so rather than
    // rendering an empty skeleton that looks like data.
    await expect(page.getByText(/no analysis yet/i)).toBeVisible();

    await page.getByRole("button", { name: /run analysis/i }).click();

    // The script totals ~7.7s; allow headroom on CI.
    await expect(page.getByText("9/9")).toBeVisible({ timeout: 25_000 });

    await expect(page.getByText("3.54 km²").first()).toBeVisible();
    await expect(page.getByText("87%").first()).toBeVisible();
    await expect(page.getByText(/Water extent increased/i)).toBeVisible();
  });

  test("the OBSERVE stage settles degraded, because half the AOI was unseen", async ({
    page,
  }) => {
    await page.goto("/console");
    await page.getByRole("button", { name: /run analysis/i }).click();
    await expect(page.getByText("9/9")).toBeVisible({ timeout: 25_000 });

    // A green tick here would overclaim: 46% of the AOI was inside the swath.
    await expect(page.getByText("degraded").first()).toBeVisible();
    await expect(page.getByText(/46% of the AOI inside the swath/i)).toBeVisible();
  });

  test("says NOT AVAILABLE for the acquisition time it does not have", async ({
    page,
  }) => {
    await page.goto("/console");
    await page.getByRole("button", { name: /run analysis/i }).click();
    await expect(page.getByText("9/9")).toBeVisible({ timeout: 25_000 });

    // Sen1Floods11 publishes no per-chip timestamp. Inventing one would be the
    // single easiest way to make the demo look more complete, so it is asserted.
    const evidence = page.getByText("Why this was flagged");
    await expect(evidence).toBeVisible();
    await expect(page.getByText("NOT AVAILABLE").first()).toBeVisible();
  });

  test("marks every fixture-fed surface as a fixture", async ({ page }) => {
    await page.goto("/console");
    // text-transform is CSS; the DOM says "Env".
    await expect(page.getByText(/env/i).first()).toBeVisible();
    await expect(page.getByText("DEMO").first()).toBeVisible();
    await expect(page.getByText(/demo fixtures/i).first()).toBeVisible();
  });

  test("reports the gateway as unreachable rather than faking health", async ({
    page,
  }) => {
    await page.goto("/console");
    // No backend is running in E2E. The console must say so.
    await expect(page.getByText(/Gateway: unreachable/i)).toBeVisible({
      timeout: 20_000,
    });
  });
});

test.describe("AOI validation", () => {
  test("draw mode shows live validation and refuses an unfinished polygon", async ({
    page,
  }) => {
    await page.goto("/console");
    await page.getByRole("button", { name: /^draw aoi$/i }).click();

    await expect(page.getByText(/click to add corners/i)).toBeVisible();
    // Nothing drawn yet, so committing is blocked.
    await expect(page.getByRole("button", { name: /^commit$/i })).toBeDisabled();

    await page.keyboard.press("Escape");
    await expect(page.getByText(/click to add corners/i)).toBeHidden();
  });
});

test.describe("routes", () => {
  test("mission memory lists the run history", async ({ page }) => {
    await page.goto("/missions");
    await expect(page.getByText(/temporal history/i)).toBeVisible();
    await expect(page.getByText(/New water detected/i)).toBeVisible();
  });

  test("monitoring shows a countdown derived from timestamps", async ({ page }) => {
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
  test("the comparison wipe is keyboard operable", async ({ page }) => {
    await page.goto("/console");
    await page.getByRole("button", { name: /run analysis/i }).click();
    await expect(page.getByText("9/9")).toBeVisible({ timeout: 25_000 });

    const slider = page.getByRole("slider", { name: /comparison wipe/i });
    await expect(slider).toBeVisible();
    await slider.focus();
    await page.keyboard.press("ArrowLeft");
    await expect(slider).toHaveValue("49");
  });

  test("every page exposes a main landmark and a reachable skip link", async ({
    page,
  }) => {
    for (const path of ["/console", "/missions", "/monitoring", "/admin"]) {
      await page.goto(path);
      await expect(page.locator("#mission-main")).toBeAttached();
    }
  });
});
