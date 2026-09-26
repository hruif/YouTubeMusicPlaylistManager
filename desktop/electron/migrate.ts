// One-time data carry-over for the rename from "YouTube Music Manager" to "YouTube Music Playlist
// Manager". The data folder is named after the app, so without this the renamed app starts empty.

import { cpSync, existsSync, rmSync } from "node:fs";
import path from "node:path";

export const LEGACY_APP_NAME = "YouTube Music Manager";

// What the app itself stores: the library cache (playlists, sidebar, custom names, archives) and
// Local Storage (UI settings). Chromium's own caches are left behind, and so is the saved sign-in:
// it's encrypted with a keychain entry named after the old app, so it can't be read anyway.
const CARRIED = ["library_cache.json", "Local Storage"];

// Copies the old app's data into `userDataDir` on the renamed app's first run. Electron creates
// `userDataDir` before any app code runs, so "first run" means it has no library cache yet (not that
// the folder is missing). Copies rather than moves, so the old folder stays as a backup. Runs before
// any window opens, so nothing has Local Storage open yet. Returns whether it copied anything.
export function migrateLegacyUserData(appDataDir: string, userDataDir: string): boolean {
  const oldDir = path.join(appDataDir, LEGACY_APP_NAME);
  if (path.resolve(oldDir) === path.resolve(userDataDir)) return false;
  if (!existsSync(path.join(oldDir, "library_cache.json"))) return false;
  if (existsSync(path.join(userDataDir, "library_cache.json"))) return false;
  for (const name of CARRIED) {
    const from = path.join(oldDir, name);
    if (!existsSync(from)) continue;
    const to = path.join(userDataDir, name);
    rmSync(to, { recursive: true, force: true });
    cpSync(from, to, { recursive: true });
  }
  return true;
}
