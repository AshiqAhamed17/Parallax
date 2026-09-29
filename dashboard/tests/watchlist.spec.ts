import { expect, test } from "@playwright/test";

test("save persists across reload and writes nothing over the network", async ({ page }) => {
  const nonGet: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET") nonGet.push(`${r.method()} ${r.url()}`);
  });

  await page.goto("/markets");
  await page.getByRole("button", { name: /save to watchlist/i }).first().click();
  await page.reload();
  await expect(page.getByRole("button", { name: /remove from watchlist/i }).first()).toBeVisible();

  await page.goto("/watchlist");
  await expect(page.locator('a[href^="/markets/demo-"]')).toHaveCount(1);

  // Acceptance: saving/unsaving is localStorage-only — no non-GET request fires.
  expect(nonGet, "no non-GET request during save/reload").toEqual([]);
});
