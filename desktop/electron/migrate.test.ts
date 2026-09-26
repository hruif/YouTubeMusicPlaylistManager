import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { LEGACY_APP_NAME, migrateLegacyUserData } from "./migrate";

let appData: string;
const oldDir = () => path.join(appData, LEGACY_APP_NAME);
const newDir = () => path.join(appData, "YouTube Music Playlist Manager");
const write = (file: string, text: string) => {
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, text);
};

beforeEach(() => {
  appData = mkdtempSync(path.join(os.tmpdir(), "ytmpm-migrate-"));
  write(path.join(oldDir(), "library_cache.json"), "old cache");
  write(path.join(oldDir(), "Local Storage", "leveldb", "000003.log"), "old settings");
  write(path.join(oldDir(), "session.bin"), "old session");
});
afterEach(() => rmSync(appData, { recursive: true, force: true }));

describe("migrateLegacyUserData", () => {
  it("carries the cache and settings into the folder Electron already created, keeping a backup", () => {
    // What Electron leaves before app code runs: the folder, with its own files but no app data.
    write(path.join(newDir(), "Preferences"), "{}");
    write(path.join(newDir(), "Local Storage", "leveldb", "LOCK"), "");

    expect(migrateLegacyUserData(appData, newDir())).toBe(true);
    expect(readFileSync(path.join(newDir(), "library_cache.json"), "utf8")).toBe("old cache");
    expect(readFileSync(path.join(newDir(), "Local Storage", "leveldb", "000003.log"), "utf8")).toBe("old settings");
    expect(existsSync(path.join(newDir(), "Local Storage", "leveldb", "LOCK"))).toBe(false);
    expect(existsSync(path.join(newDir(), "session.bin"))).toBe(false); // can't be decrypted under the new name
    expect(existsSync(path.join(oldDir(), "library_cache.json"))).toBe(true); // backup kept
  });

  it("also works when the new folder doesn't exist yet", () => {
    expect(migrateLegacyUserData(appData, newDir())).toBe(true);
    expect(readFileSync(path.join(newDir(), "library_cache.json"), "utf8")).toBe("old cache");
  });

  it("never touches a renamed app that already has its own data", () => {
    write(path.join(newDir(), "library_cache.json"), "new cache");
    expect(migrateLegacyUserData(appData, newDir())).toBe(false);
    expect(readFileSync(path.join(newDir(), "library_cache.json"), "utf8")).toBe("new cache");
  });

  it("does nothing on a fresh install or without old data", () => {
    rmSync(oldDir(), { recursive: true });
    expect(migrateLegacyUserData(appData, newDir())).toBe(false);
    expect(existsSync(newDir())).toBe(false);
  });

  it("does nothing when the data folder still has the legacy name", () => {
    expect(migrateLegacyUserData(appData, oldDir())).toBe(false);
  });
});
