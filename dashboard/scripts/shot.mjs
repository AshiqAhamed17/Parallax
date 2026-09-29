// Screenshot helper: node scripts/shot.mjs <path> <outfile> [width] [height]
// Scrolls the whole page first so scroll-triggered (whileInView) reveals fire, then captures.
import { chromium } from "@playwright/test";

const path = process.argv[2] ?? "/";
const out = process.argv[3] ?? "shot.png";
const width = Number(process.argv[4] ?? 1440);
const height = Number(process.argv[5] ?? 900);
const base = process.env.SHOT_BASE ?? "http://127.0.0.1:3000";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2 });
await page.goto(`${base}${path}`, { waitUntil: "load" });

// Scroll to the bottom in steps to trigger every in-view reveal, then back to top.
await page.evaluate(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const h = document.body.scrollHeight;
  for (let y = 0; y <= h; y += 400) {
    window.scrollTo(0, y);
    await sleep(80);
  }
  window.scrollTo(0, 0);
  await sleep(400);
});
await page.waitForTimeout(500);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log(`shot ${base}${path} -> ${out}`);
