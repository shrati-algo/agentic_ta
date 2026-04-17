import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByRole("textbox", { name: "Password" }).fill("test-pass");
  await page.getByRole("button", { name: /Sign In/i }).click();
  await expect(page).toHaveURL(/\/home$/);
}

/**
 * End-to-end flow: dashboard -> violation detail -> decision.
 *
 * Assumes `make demo` + `make dev-ui` are running and the demo replay
 * has been kicked off (the Dashboard does this automatically on mount).
 * The synthetic seed path is used as a deterministic warm-up so the
 * test doesn't depend on the 20-second replay cadence.
 */

async function seedSome(page: Page, count = 3) {
  // Hit the backend via the Vite proxy to ensure at least `count`
  // chassis exist before the table-visibility assertions run.
  const response = await page.request.post("/v1/demo/replay/start", {
    data: { interval_seconds: 0.5, max_pairs: count },
  });
  expect(response.ok(), `replay/start failed: ${response.status()}`).toBe(true);

  // Wait until the backend reports the chassis list has at least `count` rows
  await expect
    .poll(
      async () => {
        const r = await page.request.get(`/v1/chassis?page=1&page_size=1`);
        const body = await r.json();
        return body.total;
      },
      { timeout: 30_000, intervals: [1000, 1500, 2000] }
    )
    .toBeGreaterThanOrEqual(count);
}

test.describe("Dashboard", () => {
  test("loads, shows the three KPI cards, and redirects / -> /home", async ({ page }) => {
    await signIn(page);
    await expect(page).toHaveURL(/\/home$/);

    await expect(page.getByRole("heading", { name: "Violations Today" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Violation Trend" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent Alerts" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Production Details" })).toBeVisible();

    // Header
    await expect(page.getByRole("link", { name: "Home" })).toBeVisible();
    await expect(page.getByText("Live View")).toBeVisible();
  });

  test("row click opens violation detail page", async ({ page }) => {
    await seedSome(page, 3);
    await signIn(page);

    // Wait for at least one data row (skip the header row)
    const row = page.locator("tbody tr").first();
    await expect(row).toBeVisible({ timeout: 30_000 });
    await expect(row.locator("td")).not.toHaveCount(1); // not the empty/loading placeholder

    // Grab the chassis number from the row for a later assertion
    const chassisText = await row.locator("td").nth(2).innerText();
    await row.click();

    // URL now under /home/details/<uuid>
    await expect(page).toHaveURL(/\/home\/details\/[0-9a-f-]+$/);
    await expect(page.getByRole("heading", { level: 1, name: /Violation Detail/i })).toBeVisible();

    // Both camera cards rendered
    await expect(page.getByText("Cam1")).toBeVisible();
    await expect(page.getByText("Cam2")).toBeVisible();

    // Detail panel shows the chassis number we clicked
    await expect(page.getByText(chassisText.trim())).toBeVisible();

    // Back button returns to the dashboard
    await page.getByRole("button", { name: /back/i }).click();
    await expect(page).toHaveURL(/\/home$/);
  });
});
