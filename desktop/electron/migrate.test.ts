import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { LEGACY_APP_NAME, migrateLegacyUserData } from "./migrate";

let appData: string;
const oldDir = () => path.join(appData, LEGACY_APP_NAME);
const newDir = () => path.join(appData, "YouTube Music Playlist Manager");

beforeEach(() => {
  appData = mkdtempSync(path.join(os.tmpdir(), "ytmpm-migrate-"));
});
afterEach(() => rmSync(appData, { recursive: true, force: true }));

describe("migrateLegacyUserData", () => {
  it("moves the old data folder to the new name, contents intact", () => {
    mkdirSync(oldDir());
    writeFileSync(path.join(oldDir(), "library_cache.json"), "{\"version\":2}");
    expect(migrateLegacyUserData(appData, newDir())).toBe(true);
    expect(existsSync(oldDir())).toBe(false);
    expect(readFileSync(path.join(newDir(), "library_cache.json"), "utf8")).toBe("{\"version\":2}");
  });

  it("never overwrites an existing new folder", () => {
    mkdirSync(oldDir());
    mkdirSync(newDir());
    writeFileSync(path.join(newDir(), "keep.txt"), "new");
    expect(migrateLegacyUserData(appData, newDir())).toBe(false);
    expect(readFileSync(path.join(newDir(), "keep.txt"), "utf8")).toBe("new");
    expect(existsSync(oldDir())).toBe(true);
  });

  it("does nothing on a fresh install", () => {
    expect(migrateLegacyUserData(appData, newDir())).toBe(false);
    expect(existsSync(newDir())).toBe(false);
  });

  it("does nothing when the data folder already has the legacy name", () => {
    mkdirSync(oldDir());
    expect(migrateLegacyUserData(appData, oldDir())).toBe(false);
    expect(existsSync(oldDir())).toBe(true);
  });
});
