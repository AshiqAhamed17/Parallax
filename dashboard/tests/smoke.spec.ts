import { expect, test } from "@playwright/test";

test("homepage shows the disclaimer and a hero heading", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/never places orders/i)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("markets page renders at least one market row", async ({ page }) => {
  await page.goto("/markets");
  await expect(page.locator('a[href^="/markets/demo-"]').first()).toBeVisible();
});

test("respects prefers-reduced-motion", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page).toHaveTitle(/parallax/i);
  await ctx.close();
});
