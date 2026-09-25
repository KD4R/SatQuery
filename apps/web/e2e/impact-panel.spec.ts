import { expect, test } from "@playwright/test";

/**
 * Infrastructure impact panel (PRD §2D) — e2e over the deterministic demo flow.
 *
 * The hierarchy the PRD names — Flood → Roads → Hospitals — is asserted as
 * rendered structure, and so are the honesty rules: a hospital is a point feature
 * and has no linear extent, so its category total must stay NOT AVAILABLE with the
 * reason attached, and the two roads clear of the change polygons must still be
 * listed. A "0 km" or a fabricated hospital total would read as measurement; this
 * spec fails if one ever appears.
 */

test.describe("console — infrastructure impact", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/console");
    await page.getByRole("button", { name: /run analysis/i }).click();
    // The demo script totals ~7.7s; allow headroom on CI.
    await expect(page.getByText("9/9")).toBeVisible({ timeout: 25_000 });
  });

  test("builds the Flood → Roads → Hospitals hierarchy from the intersection", async ({
    page,
  }) => {
    const impact = page
      .locator(".panel-section")
      .filter({ hasText: "Infrastructure impact" });

    // Level 1 — the hazard, carrying the same measured figures as the Change
    // section (the panel mirrors them; it never invents its own totals).
    await expect(impact.getByText("New water")).toBeVisible();
    await expect(impact.getByText("3.54 km²")).toBeVisible();

    // Level 2 — categories, with affected/total counts on the chips.
    await expect(impact.getByText("Roads", { exact: true })).toBeVisible();
    await expect(impact.getByText("2/4 affected")).toBeVisible();
    await expect(impact.getByText("Hospitals", { exact: true })).toBeVisible();
    await expect(impact.getByText("1/3 affected")).toBeVisible();

    // The one aggregate the fixture can justify: 1.84 + 0.62 km inside the flood.
    await expect(impact.getByText("2.46 km")).toBeVisible();

    // Level 3 — the records themselves, OSM ids verbatim.
    await expect(impact.getByText("OSM way 98214")).toBeVisible();
    await expect(impact.getByText("OSM node 6614492182")).toBeVisible();

    await expect(impact.getByText(/Source: PostGIS/)).toBeVisible();
  });

  test("keeps the honesty markers: unknowns stay NOT AVAILABLE, clear roads stay listed", async ({
    page,
  }) => {
    const impact = page
      .locator(".panel-section")
      .filter({ hasText: "Infrastructure impact" });

    // Hospitals are point features: no affected length exists to print, and the
    // gap must carry its reason, not silently disappear.
    const unavailable = impact.locator(".readout-value-na");
    await expect(unavailable).toHaveText(/NOT AVAILABLE/);
    await expect(unavailable).toHaveAttribute("title", /linear extent/i);

    // Three records intersect the change polygons, four do not — the panel shows
    // checked-and-clear records, not a wall of hits.
    await expect(impact.locator(".impact-item.is-affected")).toHaveCount(3);
    await expect(impact.locator(".impact-item:not(.is-affected)")).toHaveCount(4);

    // A zero here would claim "measured, nothing exposed" — the exact inversion
    // of NOT AVAILABLE this console exists to prevent.
    await expect(impact.getByText("0.00 km")).toHaveCount(0);
  });
});
