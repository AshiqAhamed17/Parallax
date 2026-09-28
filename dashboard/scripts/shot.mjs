// Screenshot helper for design iteration: node scripts/shot.mjs <path> <outfile> [width] [height]
import { chromium } from "@playwright/test";

const path = process.argv[2] ?? "/";
const out = process.argv[3] ?? "shot.png";
const width = Number(process.argv[4] ?? 1440);
const height = Number(process.argv[5] ?? 900);
const base = process.env.SHOT_BASE ?? "http://127.0.0.1:3000";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 2 });
await page.goto(`${base}${path}`, { waitUntil: "networkidle" });
await page.waitForTimeout(600);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log(`shot ${base}${path} -> ${out}`);
