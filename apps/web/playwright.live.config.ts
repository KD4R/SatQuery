import { defineConfig, devices } from "@playwright/test";

/**
 * Live-mode console against a stubbed gateway (audit W12).
 *
 * playwright.config.ts covers the deterministic demo. This project builds the
 * console in LIVE mode (no NEXT_PUBLIC_DEMO_MODE) and intercepts /api/v1/* in the
 * browser, replaying run snapshots recorded from the real orchestrator
 * (e2e/live/*.json). It checks the wiring: dev sign-in, AOI gating, the per-node
 * step list, the result card, the water outline, failure and gateway-down states.
 *
 *   npm run test:e2e:live
 */

const PORT = Number(process.env.PLAYWRIGHT_LIVE_PORT ?? 3211);
const BASE = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./e2e/live",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never", outputFolder: "playwright-report-live" }]] : [["list"]],
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    {
      name: "chromium-live",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
        launchOptions: {
          // MapLibre needs WebGL; headless Chromium only offers it via SwiftShader.
          args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
          ...(process.env.PLAYWRIGHT_CHROMIUM_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH } : {}),
        },
      },
    },
  ],
  webServer: {
    command:
      `npm run build && ` +
      `rm -rf .next/standalone/.next/static .next/standalone/public && ` +
      `cp -r .next/static .next/standalone/.next/static && ` +
      `cp -r public .next/standalone/public && ` +
      `PORT=${PORT} node .next/standalone/server.js`,
    url: BASE,
    reuseExistingServer: false,
    timeout: 240_000,
    // Live mode: the demo flag must be absent. The gateway origin points nowhere;
    // every /api/v1 call is answered by page.route in the spec.
    env: { NEXT_PUBLIC_DEMO_MODE: "", GATEWAY_ORIGIN: "http://127.0.0.1:9" },
  },
});
