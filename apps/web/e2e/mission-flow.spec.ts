import { expect, test } from "@playwright/test";


const E2E_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlMmUtdXNlciIsIm9yZ19pZCI6InRlc3Qtb3JnIiwicm9sZXMiOlsiYWRtaW4iLCJvcGVyYXRvciIsImFuYWx5c3QiLCJ2aWV3ZXIiXSwic2NvcGVzIjpbXSwiZXhwIjoxODIxMDgxODcxfQ.HyrD3auADI1lB2sCTA5Oj2f9p7B9U-U-Edy2knzAIvA";

test.beforeEach(async ({ page }) => {
  // Inject auth token for live backend testing
  await page.route("**/api/v1/**", async (route) => {
    const headers = {
      ...route.request().headers(),
      Authorization: `Bearer ${E2E_TOKEN}`,
    };
    await route.continue({ headers });
  });
});

test.describe("landing", () => {
  test("names the product and offers the console", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/SatQuery AI/);
    await expect(page.getByRole("link", { name: /Mission Console/i }).first()).toBeVisible();
  });
});

test.describe("console — live run", () => {
  test("runs the full flow and reaches EVIDENCE READY", async ({ page }) => {
    // 1. Go to dashboard
    await page.goto("/dashboard");

    // 2. Click run
    await page.locator('button.send').click();

    // 4. Wait for EVIDENCE READY
    await expect(page.getByText("EVIDENCE READY")).toBeVisible({ timeout: 60_000 });

    // 5. Assert summary or confidence appears
    await expect(page.locator('.section-strip')).toContainText("Mission complete", { timeout: 10_000 });
  });
});
