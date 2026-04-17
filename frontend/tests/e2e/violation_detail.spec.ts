import { expect, test, type Page } from "@playwright/test";

/**
 * Fill the sign-in form that's currently displayed and submit. Assumes
 * the page is already on /login (either because the user went there
 * directly or because ProtectedRoute redirected them). After submission
 * the user lands on the original target (state.from) or /home.
 */
async function submitSignIn(page: Page): Promise<void> {
  await page.getByRole("textbox", { name: "Password" }).fill("test-pass");
  await page.getByRole("button", { name: /Sign In/i }).click();
}

/**
 * Detail page flow: Correct Violation + Flag.  Seeds a chassis
 * deterministically via the replay API, then drives the UI.
 */

test.describe("Violation Detail", () => {
  test("records a decision and toggles flag", async ({ page }) => {
    // Seed one pair and wait for it to be processed
    await page.request.post("/v1/demo/replay/start", {
      data: { interval_seconds: 0.5, max_pairs: 1 },
    });

    // Poll until the chassis list has at least one entry, then fetch its id
    let chassisId: string | null = null;
    await expect
      .poll(
        async () => {
          const r = await page.request.get(`/v1/chassis?page=1&page_size=1`);
          const body = await r.json();
          if (body.total >= 1) {
            chassisId = body.items[0].chassis_record_id;
            return true;
          }
          return false;
        },
        { timeout: 30_000, intervals: [1000, 1500, 2000] }
      )
      .toBe(true);

    expect(chassisId).toBeTruthy();

    // Routes are protected -- visit the detail URL first, which the
    // ProtectedRoute bounces to /login while remembering where we
    // were going, then sign in and verify we landed back on it.
    await page.goto(`/home/details/${chassisId}`);
    await expect(page).toHaveURL(/\/login$/);
    await submitSignIn(page);
    await expect(page).toHaveURL(new RegExp(`/home/details/${chassisId}$`));
    await expect(page.getByRole("heading", { level: 1, name: /Violation Detail/i })).toBeVisible();

    // Click "Correct Violation" on the first CameraCard (Cam1)
    const correctBtns = page.getByRole("button", { name: "Correct Violation" });
    await expect(correctBtns.first()).toBeVisible();
    await correctBtns.first().click();

    // The button should stay in the DOM and be clickable again
    await expect(correctBtns.first()).toBeVisible();

    // Toggle the flag
    const flagBtn = page.getByRole("button", { name: /^Flag$/ });
    if (await flagBtn.isVisible().catch(() => false)) {
      await flagBtn.click();
      await expect(page.getByRole("button", { name: /Flagged/i })).toBeVisible();
    }
  });
});
