import { expect, test, type ConsoleMessage, type Page } from "@playwright/test";

/**
 * Console routing (P5-01, P5-15, P5-17).
 *
 * The regression this guards: the landing page's Console button opened a superseded
 * screen (/console) while the real mission console lived at /dashboard, reachable
 * only by typing the URL. The canonical console is /dashboard; every other path
 * either is a section of it or redirects into it.
 *
 * Reduced motion is emulated throughout so the landing page's opening animation is
 * skipped by its own reduced-motion path rather than raced with timers.
 */

test.use({ reducedMotion: "reduce" });

const CONSOLE = "/dashboard";

/** The canonical console, recognised by content rather than by URL alone. */
async function expectMissionConsole(page: Page) {
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Mission overview");
  await expect(page.getByRole("textbox", { name: /mission query/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /run analysis/i })).toBeVisible();
  await expect(page.locator("#mission-main")).toBeAttached();
}

/**
 * Console errors that matter. The only tolerated one is the browser's own
 * "Failed to load resource" line for /api/v1/*: the E2E stack has no gateway, and
 * the console is required to say so (see mission-flow.spec.ts) rather than hide it.
 */
function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m: ConsoleMessage) => {
    if (m.type() !== "error") return;
    const text = m.text();
    if (/Failed to load resource/i.test(text) && /5\d\d|ERR_/i.test(text)) return;
    errors.push(`console.error: ${text}`);
  });
  return errors;
}

test.describe("landing -> console", () => {
  test("the landing page loads without console errors", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/");
    await expect(page).toHaveTitle(/SatQuery AI/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Ask a question");
    expect(errors).toEqual([]);
  });

  test("every Console link on the landing page targets the canonical console", async ({
    page,
  }) => {
    await page.goto("/");
    // The skip link also says "console" but targets an in-page anchor.
    const hrefs = await page
      .locator("a:not(.skip-link)")
      .filter({ hasText: /console/i })
      .evaluateAll((els) => els.map((e) => e.getAttribute("href")));
    expect(hrefs.length).toBeGreaterThanOrEqual(3);
    for (const href of hrefs) expect(href).toBe(CONSOLE);
  });

  test("the hero's Console button opens the mission console", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /enter mission console/i }).click();
    await expect(page).toHaveURL(new RegExp(`${CONSOLE}$`));
    await expectMissionConsole(page);
  });

  test("the nav's Open console button opens the mission console", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /^open console/i }).click();
    await expect(page).toHaveURL(new RegExp(`${CONSOLE}$`));
    await expectMissionConsole(page);
  });

  test("browser back and forward move between landing and console", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /enter mission console/i }).click();
    await expectMissionConsole(page);

    await page.goBack();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Ask a question");

    await page.goForward();
    await expect(page).toHaveURL(new RegExp(`${CONSOLE}$`));
    await expectMissionConsole(page);
  });
});

test.describe("the canonical console URL", () => {
  test("opens directly, with no console errors and gateway-only API traffic", async ({
    page,
    baseURL,
  }) => {
    const errors = collectErrors(page);
    const foreign: string[] = [];
    // The Esri basemap is the one documented non-gateway origin (licensed
    // imagery, listed in next.config.ts's CSP). Its tiles are answered locally
    // with a transparent pixel so this test does not depend on internet access.
    const BASEMAP = /^https:\/\/[a-z]+\.arcgisonline\.com\//;
    await page.route(BASEMAP, (route) =>
      route.fulfill({
        status: 200,
        contentType: "image/png",
        body: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
          "base64",
        ),
      }),
    );
    page.on("request", (req) => {
      const url = new URL(req.url());
      if (BASEMAP.test(req.url())) return;
      if (url.origin !== new URL(baseURL!).origin) foreign.push(req.url());
      else if (url.pathname.startsWith("/api/") && !url.pathname.startsWith("/api/v1/")) {
        foreign.push(req.url());
      }
    });

    await page.goto(CONSOLE);
    await expectMissionConsole(page);
    // Let the health probe settle so its request is part of what is checked.
    await expect(
      page.getByRole("contentinfo", { name: /system telemetry/i }),
    ).toContainText(/unreachable/i, { timeout: 20_000 });

    expect(errors).toEqual([]);
    expect(foreign, "the browser may call the gateway path (/api/v1) and the basemap, nothing else").toEqual(
      [],
    );
  });

  test("survives a browser refresh, including mid-page state resets", async ({ page }) => {
    await page.goto(CONSOLE);
    await expectMissionConsole(page);
    await page.reload();
    await expect(page).toHaveURL(new RegExp(`${CONSOLE}$`));
    await expectMissionConsole(page);
  });

  test("a deep link into a section survives a refresh", async ({ page }) => {
    await page.goto("/dashboard/monitoring");
    await expect(page.getByText(/next observation/i).first()).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(/\/dashboard\/monitoring$/);
    await expect(page.getByText(/next observation/i).first()).toBeVisible();
  });

  test("section navigation is client-side and back returns to the console", async ({
    page,
  }) => {
    await page.goto(CONSOLE);
    await page.getByRole("radio", { name: /monitoring/i }).click();
    await expect(page).toHaveURL(/\/dashboard\/monitoring$/);
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`${CONSOLE}$`));
    await expectMissionConsole(page);
  });
});

test.describe("superseded routes redirect, never render a second console", () => {
  test("/console lands on the canonical console", async ({ page }) => {
    await page.goto("/console");
    await expect(page).toHaveURL(new RegExp(`${CONSOLE}$`));
    await expectMissionConsole(page);
  });

  test("a redirect keeps the query string", async ({ page }) => {
    await page.goto("/console?mission=msn-1");
    await expect(page).toHaveURL(/\/dashboard\?mission=msn-1$/);
  });

  test("the old section paths land on their dashboard equivalents", async ({ page }) => {
    const cases: [string, RegExp][] = [
      ["/monitoring", /\/dashboard\/monitoring$/],
      ["/missions", /\/dashboard\/history$/],
      ["/admin", /\/dashboard\/admin$/],
      ["/missions/msn-2026-0914-assam-01/report", /\/dashboard\/reports\/msn-2026-0914-assam-01$/],
      ["/dashboard/map", /\/dashboard$/],
      ["/dashboard/preview", /\/dashboard$/],
    ];
    for (const [from, to] of cases) {
      await page.goto(from);
      await expect(page, `${from} should redirect`).toHaveURL(to);
    }
  });

  test("an unknown route is a 404, not a silent redirect to the console", async ({
    page,
  }) => {
    const response = await page.goto("/definitely-not-a-route");
    expect(response?.status()).toBe(404);
  });
});
