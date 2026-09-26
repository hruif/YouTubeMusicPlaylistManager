// Website screenshots of the real UI with demo data (no account). From desktop/:
//   npm run build && node scripts/screenshots/take.mjs
// Writes PNGs to ../docs/screenshots/.
import { _electron as electron } from "playwright-core";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(here, "../../../docs/screenshots");
mkdirSync(out, { recursive: true });

const app = await electron.launch({ args: [path.join(here, "main.cjs")] });
const page = await app.firstWindow();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Fresh app state for each scene: which playlists are selected, and the theme.
async function scene(selected, theme = "dark") {
  await page.evaluate(
    ([sel, th]) =>
      localStorage.setItem("ytm.ui", JSON.stringify({ selected: sel, theme: th, autoRefreshOnLaunch: false, checkUpdates: false })),
    [selected, theme],
  );
  await page.reload();
  await page.locator(".song-row").first().waitFor();
  await sleep(400);
}
async function shot(name) {
  await sleep(300);
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(`wrote ${name}.png`);
}

await page.waitForLoadState("domcontentloaded");

// 1. The main view: two playlists combined, songs in both shown once.
await scene(["night", "sunday"]);
await shot("main");

await app.close();
