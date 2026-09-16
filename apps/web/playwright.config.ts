import { defineConfig, devices } from "@playwright/test";

/**
 * P5-17.
 *
 * The suite runs against the deterministic demo (NEXT_PUBLIC_DEMO_MODE=1), because
 * that is the path the judges will see and the only one whose figures are constants
 * rather than tolerances. It needs no backend: the console is expected to report the
 * gateway as unreachable, and one of the tests asserts exactly that.
 */

const PORT = Number(process.env.PLAYWRIGHT_PORT ?? 3000);
const BASE = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
    // The console is designed for desktop first; the mobile fallback has its own
    // coverage rather than being the default viewport here.
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // Normally Playwright uses the browser it downloaded. Some sandboxes and
        // CI images ship a Chromium at a fixed path and block the download CDN;
        // PLAYWRIGHT_CHROMIUM_PATH lets those run the same suite unchanged.
        ...(process.env.PLAYWRIGHT_CHROMIUM_PATH
          ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } }
          : {}),
      },
    },
  ],
  webServer: undefined,
});
