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
const row = (title) => page.locator(".song-row", { hasText: title }).first();
async function shot(name) {
  await sleep(300);
  await page.screenshot({ path: path.join(out, `${name}.png`) });
  console.log(`wrote ${name}.png`);
}

await page.waitForLoadState("domcontentloaded");

// 1. The main view: two playlists combined, songs in both shown once.
await scene(["night", "sunday"]);
await shot("main");

// 2. Several songs selected, with the actions for them above the list.
await scene(["night", "sunday", "gym"]);
await row("Blinding Lights").click();
await row("Heat Waves").click({ modifiers: ["Meta"] });
await row("Midnight City").click({ modifiers: ["Meta"] });
await page.mouse.move(5, 700);
await shot("select");

// 3. Filters: what three playlists have in common.
await scene(["night", "sunday", "road"]);
await page.getByRole("button", { name: "Filter" }).click();
await page.getByLabel("In more than one playlist").check();
await shot("filter");
await page.keyboard.press("Escape");

// 4. Undo after removing songs.
await scene(["road"]);
await row("Take On Me").click();
await row("Mr. Blue Sky").click({ modifiers: ["Meta"] });
await page.keyboard.press("Delete");
await page.getByRole("button", { name: "Confirm" }).click();
await page.getByRole("button", { name: "Undo" }).waitFor();
await page.mouse.move(700, 740); // hovering keeps the toast up
await page.locator(".toast").hover();
await shot("undo");

// 5. Light theme, with a song's details open.
await scene(["focus", "night"], "light");
await row("Holocene").click();
await row("Holocene").click();
await page.getByRole("dialog").waitFor();
await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
await shot("details-light");

await app.close();
