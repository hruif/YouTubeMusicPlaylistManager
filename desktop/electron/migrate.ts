// One-time data-folder move for the rename from "YouTube Music Manager" to "YouTube Music Playlist
// Manager". The data folder (library cache, UI settings, session) is named after the app, so
// without this the renamed app would start empty.

import { existsSync, renameSync } from "node:fs";
import path from "node:path";

export const LEGACY_APP_NAME = "YouTube Music Manager";

// Moves <appData>/<legacy name> to `userDataDir` when only the old folder exists. Never merges or
// overwrites: if the new folder already exists, the old one is left alone. Returns whether it moved.
export function migrateLegacyUserData(appDataDir: string, userDataDir: string): boolean {
  const oldDir = path.join(appDataDir, LEGACY_APP_NAME);
  if (path.resolve(oldDir) === path.resolve(userDataDir)) return false;
  if (existsSync(userDataDir) || !existsSync(oldDir)) return false;
  renameSync(oldDir, userDataDir);
  return true;
}
