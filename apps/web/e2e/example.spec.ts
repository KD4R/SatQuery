import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  // P5-17 demo mode deterministic loading validation
  await page.goto('/');
  await expect(page).toHaveTitle(/SatQuery AI/);
});
