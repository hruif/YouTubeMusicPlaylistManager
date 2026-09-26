import { afterEach, describe, expect, it, vi } from "vitest";

const { electronApp } = vi.hoisted(() => ({
  electronApp: {
    isPackaged: true,
    getPath: vi.fn(() => "/Applications/YouTube Music Playlist Manager.app/Contents/MacOS/YouTube Music Playlist Manager"),
  },
}));

vi.mock("electron", () => ({ app: electronApp }));

import { installedAppPath, stageUpdate } from "./updater";

afterEach(() => {
  electronApp.isPackaged = true;
  electronApp.getPath.mockReturnValue("/Applications/YouTube Music Playlist Manager.app/Contents/MacOS/YouTube Music Playlist Manager");
  vi.restoreAllMocks();
});

describe("installedAppPath", () => {
  it("resolves the enclosing app bundle for a packaged executable", () => {
    expect(installedAppPath()).toBe("/Applications/YouTube Music Playlist Manager.app");
  });

  it("rejects development and non-app executable locations", () => {
    electronApp.isPackaged = false;
    expect(installedAppPath()).toBeNull();
    electronApp.isPackaged = true;
    electronApp.getPath.mockReturnValue("/usr/local/bin/ytmpm");
    expect(installedAppPath()).toBeNull();
  });
});

describe("stageUpdate guardrails", () => {
  it.each([
    "http://github.com/hruif/release.zip",
    "https://github.com.evil.test/release.zip",
    "https://example.test/release.zip",
    "not a url",
  ])("rejects an untrusted update URL before downloading: %s", async (url) => {
    vi.spyOn(process, "platform", "get").mockReturnValue("darwin");
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await expect(stageUpdate(url, vi.fn())).rejects.toThrow("untrusted URL");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects in-place updates outside macOS before downloading", async () => {
    vi.spyOn(process, "platform", "get").mockReturnValue("linux");
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await expect(stageUpdate("https://github.com/hruif/release.zip", vi.fn())).rejects.toThrow("macOS only");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects a trusted update when the app is not installed as a bundle", async () => {
    vi.spyOn(process, "platform", "get").mockReturnValue("darwin");
    electronApp.isPackaged = false;
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    await expect(stageUpdate("https://github.com/hruif/release.zip", vi.fn())).rejects.toThrow("installed app");
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
