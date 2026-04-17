import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright smoke-test config.
 *
 * Expects the backend + Vite dev server to already be running:
 *   Terminal 1: make demo
 *   Terminal 2: make dev-ui
 *
 * Then: cd frontend && npm run test:e2e
 *
 * (Set the PLAYWRIGHT_BASE_URL env var to override :5173 if you've
 * started the single-port production build on :8000 instead.)
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
