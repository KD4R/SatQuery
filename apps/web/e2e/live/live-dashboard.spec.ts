import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Live console wiring (audit W1–W12) against a stubbed gateway.
 *
 * The run snapshots in this folder were recorded from the real agent
 * orchestrator with only the STAC search and the inference call stubbed; they
 * are replayed one per poll, the way GET /agent/runs/{job_id} walks through the
 * statuses the agent persists after each node.
 */

type Snapshots = { snapshots: Record<string, unknown>[] };
const load = (f: string) => (JSON.parse(readFileSync(join(__dirname, f), "utf8")) as Snapshots).snapshots;
const COMPLETED = load("run-completed.json");
const FAILED = load("run-failed.json");

const EXTENT = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [[[92.65, 26.34], [92.72, 26.35], [92.7, 26.38], [92.65, 26.34]]] },
    },
  ],
};

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
}

async function stubGateway(page: Page, snapshots: Record<string, unknown>[] | "down") {
  let polls = 0;
  await page.route(/arcgisonline\.com/, (r) => r.fulfill({ status: 404, body: "" }));
  await page.route(/nominatim\.openstreetmap\.org/, (r) =>
    json(r, 200, [
      { display_name: "Nagaon, Assam, India", lat: "26.36", lon: "92.70", boundingbox: ["26.28", "26.46", "92.58", "92.82"], type: "city" },
    ]),
  );
  await page.route("**/api/v1/**", (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (snapshots === "down") return route.fulfill({ status: 502, body: "Bad Gateway" });
    if (path.endsWith("/health")) return json(route, 200, { status: "ok", service: "gateway" });
    if (path.endsWith("/auth/dev-token"))
      return json(route, 200, { access_token: "e2e.token", token_type: "bearer", expires_in: 600, org_id: "org-dev", roles: ["analyst"] });
    if (path.endsWith("/missions") && route.request().method() === "POST")
      return json(route, 201, { id: "msn-e2e", name: "e2e", description: null, status: "draft", aoi_ids: [], organisation_id: "org-dev", created_by: "e2e", created_at: "", updated_at: "" });
    if (path.endsWith("/agent/execute")) {
      polls = 0;
      const body = route.request().postDataJSON() as Record<string, unknown>;
      expect(body.aoi).toBeTruthy();
      expect(route.request().headers().authorization).toBe("Bearer e2e.token");
      return json(route, 202, { job_id: "job_e2e", mission_id: "msn-e2e", status: "ACCEPTED", message: "ok", trace_id: "tr-e2e" });
    }
    if (path.includes("/agent/runs/")) {
      const snap = snapshots[Math.min(polls, snapshots.length - 1)];
      polls++;
      return json(route, 200, snap);
    }
    if (path.endsWith("/extent")) return json(route, 200, EXTENT);
    return json(route, 404, { code: "NOT_FOUND", message: path, details: [], trace_id: null });
  });
}

/** Step 1 · Where: search a place and use it as the area. */
async function setAoiFromPlace(page: Page) {
  await page.getByLabel("Search a place").fill("Nagaon");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("option").first().click();
  await page.getByRole("button", { name: /use this place/i }).click();
}

/** Step 1 · Where, the manual way: the rail's Rectangle button, then two map clicks. */
async function drawRectangle(page: Page) {
  await page.getByLabel("Search a place").fill("Nagaon");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("option").first().click();
  await page.waitForTimeout(1500); // fly-to animation
  const box = (await page.locator(".sqd-map canvas").boundingBox())!;
  await page.getByRole("region", { name: "Where" }).getByRole("button", { name: /rectangle/i }).click();
  // Wait for the map to enter drawing mode before placing corners.
  await expect(page.getByText(/click one corner/i)).toBeVisible();
  await page.mouse.click(box.x + box.width * 0.35, box.y + box.height * 0.35);
  await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.65);
}

const drawAoi = setAoiFromPlace;

test.describe("live console against a stubbed gateway", () => {
  test("Run stays locked until the area is set; the step bar points at the next step (W2)", async ({ page }) => {
    await stubGateway(page, COMPLETED);
    await page.goto("/dashboard");
    const steps = page.getByRole("navigation", { name: "Mission steps" });
    await expect(page.getByRole("button", { name: /run analysis/i })).toBeDisabled();
    await expect(page.getByText(/set an area in step 1/i)).toBeVisible();
    const stepButton = (n: number) => steps.getByRole("button").nth(n);
    await expect(stepButton(0)).toHaveAttribute("aria-current", "step"); // Where
    await drawRectangle(page);
    await expect(page.getByRole("button", { name: /run analysis/i })).toBeEnabled();
    await expect(page.getByRole("region", { name: "Where" }).getByText("Area set")).toBeVisible();
    await expect(stepButton(3)).toHaveAttribute("aria-current", "step"); // Run
  });

  test("dates: presets and a custom range are sent as the temporal window (F5)", async ({ page }) => {
    await stubGateway(page, COMPLETED);
    let sent: unknown = null;
    page.on("request", (req) => {
      if (req.url().endsWith("/agent/execute")) sent = (req.postDataJSON() as Record<string, unknown>).temporal_window;
    });
    await page.goto("/dashboard");
    await setAoiFromPlace(page);
    const when = page.getByRole("region", { name: "When" });
    await when.getByRole("button", { name: "30 days" }).click();
    await expect(when.getByText(/· 31 days/)).toBeVisible();
    await when.getByRole("button", { name: "Custom" }).click();
    await when.getByLabel("Start date").fill("2024-06-29");
    await when.getByLabel("End date").fill("2024-07-06");
    await expect(when.getByText("29 Jun 2024 → 6 Jul 2024 · 8 days")).toBeVisible();
    // The step bar's Run step runs the mission once the steps above are done.
    await page.getByRole("navigation", { name: "Mission steps" }).getByRole("button").nth(3).click();
    await expect.poll(() => sent).toEqual({ start: "2024-06-29T00:00:00Z", end: "2024-07-06T23:59:59Z" });
  });

  test("a completed run shows the measured area, its basis and the outline (W1, W4, W7, W8)", async ({ page }) => {
    await stubGateway(page, COMPLETED);
    await page.goto("/dashboard");
    await drawAoi(page);
    await page.getByRole("button", { name: /run analysis/i }).click();

    const result = page.getByRole("region", { name: "Result" });
    await expect(result).toBeVisible({ timeout: 40_000 });
    await expect(result.getByText("12.35")).toBeVisible();
    await expect(result.getByText("Model not calibrated")).toBeVisible();
    await expect(result.getByText("S1_NEW_FULL")).toBeVisible();
    await expect(result.getByText("1 water polygon")).toBeVisible();
    await expect(page.getByText("7/7")).toBeVisible();
    await expect(page.getByText(/5 scene\(s\) in 2024-06-29/)).toBeVisible();
    await expect(page.getByLabel("Map layers").getByText("Water extent")).toBeVisible();

    // Detail under the map comes from the run, not from fixtures.
    await expect(page.getByRole("region", { name: "What was searched" })).toContainText("92.600, 26.300, 92.800, 26.450");
    await expect(page.getByRole("region", { name: "Why" })).toContainText("Sentinel-1 SAR");
  });

  test("the trace is a real dialog that closes on Escape (F10)", async ({ page }) => {
    await stubGateway(page, COMPLETED);
    await page.goto("/dashboard");
    await drawAoi(page);
    await page.getByRole("button", { name: /run analysis/i }).click();
    await page.getByRole("region", { name: "Result" }).getByRole("button", { name: /open trace/i }).click({ timeout: 40_000 });
    const dialog = page.getByRole("dialog", { name: /run/i });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("button", { name: "Close trace" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });

  test("a failed run says why and what to try, with no zero figures (W3, F3)", async ({ page }) => {
    await stubGateway(page, FAILED);
    await page.goto("/dashboard");
    await drawAoi(page);
    await page.getByRole("button", { name: /run analysis/i }).click();
    const failure = page.getByRole("alert").filter({ hasText: "NO_SCENES_IN_WINDOW" });
    await expect(failure).toBeVisible({ timeout: 40_000 });
    await expect(failure).toContainText(/No scenes intersect the AOI/);
    await expect(failure).toContainText(/Widen the date range/);
    await expect(page.getByRole("region", { name: "Result" })).toHaveCount(0);
  });

  test("an unreachable gateway is named as such, with Retry (W11)", async ({ page }) => {
    await stubGateway(page, "down");
    await page.goto("/dashboard");
    await drawAoi(page);
    await page.getByRole("button", { name: /run analysis/i }).click();
    const failure = page.getByRole("alert").filter({ hasText: /gateway unreachable/i });
    await expect(failure).toBeVisible({ timeout: 20_000 });
    await expect(failure.getByRole("button", { name: /retry/i })).toBeVisible();
  });
});
