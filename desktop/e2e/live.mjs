// Live end-to-end check of undo, feedback and errors against the real app and a real, signed-in
// YouTube Music account:
//
//   npm run e2e:live            (quit the app first; it runs one copy at a time)
//
// It never edits your playlists. It copies 5 songs from the first sidebar playlist with enough
// songs into a new playlist named "zz ytmpm e2e <time>", runs every edit against that playlist,
// and deletes it at the end (also on failure). Your sidebar selection is put back afterwards.
//
// Playlist order is read from the app's cache file after a refresh, which is YouTube Music's
// real order, since the song list on screen is sorted.

import { _electron as electron } from "playwright-core";
import { readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const APP = path.resolve(
  "release",
  `mac-${process.arch}`,
  "YouTube Music Playlist Manager.app",
  "Contents",
  "MacOS",
  "YouTube Music Playlist Manager",
);
const CACHE = path.join(os.homedir(), "Library", "Application Support", "YouTube Music Playlist Manager", "library_cache.json");
const TEST_NAME = `zz ytmpm e2e ${new Date().toISOString().slice(0, 16).replace("T", " ")}`;

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const readCache = () => JSON.parse(readFileSync(CACHE, "utf8"));

const app = await electron.launch({ executablePath: APP });
const page = await app.firstWindow();
// Surface the app's own warnings (e.g. why an undo couldn't restore positions).
for (const stream of [app.process().stdout, app.process().stderr])
  stream?.on("data", (d) => String(d).split("\n").filter((l) => /restoreVideos|Error/.test(l)).forEach((l) => console.log(`  app: ${l.trim()}`)));
page.setDefaultTimeout(60_000);

// Wait until nothing is running: no progress in the header and the Refresh button enabled.
async function idle() {
  await sleep(400); // let the action start before checking that it finished
  await page.waitForFunction(() => !document.querySelector(".status .progress-bar, .status .spinner"));
  await sleep(1200); // the cache file is saved a moment after changes
}
// Re-read the selected playlists from YouTube Music; retry once because a just-made edit can
// take a moment to show up in YouTube's own responses.
async function refresh() {
  await page.keyboard.press("Meta+r");
  await idle();
}
const orderOf = (id) => (readCache().tracksByPlaylist[id] ?? []).map((t) => t.videoId);
const row = (videoId) => page.locator(`[id="song-${videoId}"]`);
// The song list only draws rows on screen, so search for a song before clicking it. The selection
// survives searching. Leaves the search empty and unfocused, so keys go to the song list.
async function clickSong(videoId, title, modifiers = []) {
  const search = page.getByRole("searchbox", { name: "Search songs" });
  await search.fill(title);
  await row(videoId).click({ modifiers });
  await search.fill("");
  await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
}
async function setSidebar(title, on) {
  const box = page.getByRole("checkbox", { name: title, exact: true });
  if ((await box.isChecked()) !== on) await box.click();
}
async function waitOrder(id, expected, label) {
  for (let i = 0; i < 4; i++) {
    const got = orderOf(id);
    if (JSON.stringify(got) === JSON.stringify(expected)) return check(label, true);
    await sleep(3000);
    await refresh();
  }
  check(label, false, `expected ${expected.join(",")} got ${orderOf(id).join(",")}`);
}

let testId = null;
let savedUi = null;
try {
  await page.getByRole("heading", { name: "YouTube Music Playlist Manager", level: 1 }).waitFor();
  savedUi = await page.evaluate(() => localStorage.getItem("ytm.ui"));
  await idle();

  // ---- Source playlist and throwaway copy ----
  const cache = readCache();
  const source = cache.playlists.find((p) => cache.shown.includes(p.id) && new Set((cache.tracksByPlaylist[p.id] ?? []).map((t) => t.videoId)).size >= 6);
  if (!source) throw new Error("Need a sidebar playlist with at least 6 loaded songs.");
  const sourceIds = [...new Set(cache.tracksByPlaylist[source.id].map((t) => t.videoId))];
  const picked = sourceIds.slice(0, 5);
  const extra = sourceIds[5];
  const titleOf = (id) => cache.tracksByPlaylist[source.id].find((t) => t.videoId === id).title;
  console.log(`Source: "${source.title}". Test playlist: "${TEST_NAME}".`);

  for (const p of cache.playlists) if (cache.shown.includes(p.id) && p.id !== source.id) await setSidebar(p.title, false);
  await setSidebar(source.title, true);
  await clickSong(picked[0], titleOf(picked[0]));
  for (const id of picked.slice(1)) await clickSong(id, titleOf(id), ["Meta"]);
  await page.getByRole("button", { name: "New playlist" }).click();
  await page.getByRole("textbox", { name: "Playlist name" }).fill(TEST_NAME);
  await page.getByRole("button", { name: "Create" }).click();
  await page.getByText(`Created “${TEST_NAME}”`).waitFor();
  check("result toast after creating a playlist", true);
  await idle();
  testId = readCache().playlists.find((p) => p.title === TEST_NAME)?.id;
  if (!testId) throw new Error("Couldn't find the new playlist in the cache.");

  await setSidebar(source.title, false);
  await setSidebar(TEST_NAME, true);
  await sleep(3000);
  await refresh();
  const original = orderOf(testId);
  check("test playlist has the 5 songs", original.length === 5, original.join(","));

  // ---- Undo a removal from the middle (toast button) ----
  await page.keyboard.press("Escape");
  await row(original[1]).click();
  await row(original[2]).click({ modifiers: ["Meta"] });
  await page.keyboard.press("Delete");
  await page.getByRole("button", { name: "Confirm" }).click();
  const undo = page.getByRole("button", { name: "Undo" });
  await undo.waitFor();
  check("removal offers Undo in its toast", true);
  await idle();
  const afterRemove = orderOf(testId);
  check("removal took the 2 songs out", afterRemove.length === 3 && !afterRemove.includes(original[1]), afterRemove.join(","));
  await undo.click();
  await page.getByText(/^Put 2 back in/).waitFor();
  await idle();
  await waitOrder(testId, original, "Undo puts 2 middle songs back in their original places");

  // ---- Undo removing the last song (⌘Z) ----
  await page.keyboard.press("Escape");
  await row(original[4]).click();
  await page.keyboard.press("Delete");
  await page.getByRole("button", { name: "Confirm" }).click();
  await page.getByRole("button", { name: "Undo" }).waitFor();
  await idle();
  // ⌘Z inside the search box belongs to the box.
  await page.getByRole("searchbox", { name: "Search songs" }).click();
  await page.keyboard.press("Meta+z");
  await sleep(500);
  check("⌘Z in the search box doesn't undo a playlist edit", (await page.getByRole("button", { name: "Undo" }).count()) === 1);
  await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : null));
  await page.keyboard.press("Meta+z");
  await page.getByText(/^Put 1 back in/).waitFor();
  await idle();
  await waitOrder(testId, original, "⌘Z puts the last song back at the end");

  // ---- Undo an add ----
  await setSidebar(source.title, true);
  await page.keyboard.press("Escape");
  await clickSong(extra, titleOf(extra));
  await page.getByRole("button", { name: "Add to…" }).click();
  const picker = page.getByRole("dialog", { name: /^Add 1 song to/ });
  await picker.getByRole("button", { name: new RegExp(TEST_NAME) }).click();
  await page.getByText(`Added 1 to ${TEST_NAME}`).waitFor();
  await idle();
  check("add put the song in", orderOf(testId).includes(extra));
  await page.getByRole("button", { name: "Undo" }).click();
  await page.getByText(/^Took 1 back out of/).waitFor();
  await setSidebar(source.title, false);
  await idle();
  await waitOrder(testId, original, "Undo of an add removes only the added song");

  // ---- Errors ----
  await page.getByRole("button", { name: "Manage playlists" }).click();
  await page.getByRole("textbox", { name: "Playlist link" }).fill("not a playlist link");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const alert = page.getByRole("alert");
  await alert.waitFor();
  check("a bad link shows an error in the header", (await alert.textContent()).includes("Couldn't find a playlist id"));
  check("that error offers no Retry (retrying can't help)", (await alert.getByRole("button", { name: "Retry" }).count()) === 0);
  await page.keyboard.press("Escape"); // closes Manage playlists (the error stays)
  check("closing the dialog leaves the error up", (await page.getByRole("alert").count()) === 1);
  await refresh();
  check("starting another action clears the error", (await page.getByRole("alert").count()) === 0);

  await page.getByRole("button", { name: "Manage playlists" }).click();
  await page.getByRole("textbox", { name: "Playlist link" }).fill("still not a link");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.getByRole("alert").waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Dismiss error" }).click();
  check("an error can be dismissed", (await page.getByRole("alert").count()) === 0);
} catch (err) {
  check("run completed", false, err instanceof Error ? err.message : String(err));
} finally {
  // ---- Clean up: delete the throwaway playlist and forget its archive ----
  try {
    if (testId) {
      await page.keyboard.press("Escape");
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "Manage playlists" }).click();
      const manage = page.getByRole("dialog", { name: "Manage playlists" });
      await manage.getByRole("textbox", { name: "Filter playlists" }).fill(TEST_NAME);
      await manage.locator("label.pl-row", { hasText: TEST_NAME }).click({ button: "right" });
      await page.getByRole("menuitem", { name: "Delete playlist…" }).click();
      await page.getByRole("textbox", { name: "Playlist name to confirm" }).fill(TEST_NAME);
      await page.getByRole("button", { name: "Delete", exact: true }).click();
      await page.getByText(`Deleted “${TEST_NAME}”`).waitFor();
      await idle();
      await page.getByRole("button", { name: "Close" }).click().catch(() => {});
      await page.getByRole("button", { name: /Queues and recently deleted/ }).click();
      await page.getByRole("menuitem", { name: /Recently deleted/ }).click();
      const deleted = page.getByRole("dialog", { name: "Recently deleted" });
      await deleted.locator(".pl-row", { hasText: TEST_NAME }).getByRole("button", { name: "Forget" }).click();
      await page.keyboard.press("Escape");
      await idle();
      const after = readCache();
      check("cleanup: test playlist deleted", !after.playlists.some((p) => p.id === testId));
      check("cleanup: its Recently deleted entry forgotten", !after.deleted.some((d) => d.title === TEST_NAME));
    }
    if (savedUi) await page.evaluate((ui) => localStorage.setItem("ytm.ui", ui), savedUi);
  } catch (err) {
    check("cleanup", false, `${err instanceof Error ? err.message : err}. Delete "${TEST_NAME}" by hand.`);
  }
  await app.close();
}

const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
