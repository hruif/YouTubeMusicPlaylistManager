import { describe, expect, it } from "vitest";
import { findLatestUpdate } from "./update";

describe("findLatestUpdate", () => {
  it("returns the newest stable desktop release newer than the current app", () => {
    const update = findLatestUpdate(
      [
        {
          tag_name: "desktop-v0.3.1",
          html_url: "https://example.test/release/0.3.1",
          assets: [{ name: "YouTube.Music.Manager-0.3.1-universal.dmg", browser_download_url: "https://example.test/app.dmg" }],
        },
        { tag_name: "v0.6.0", html_url: "https://example.test/python" },
        { tag_name: "desktop-v0.4.0", prerelease: true, html_url: "https://example.test/prerelease" },
      ],
      "0.3.0",
    );

    expect(update).toEqual({ version: "0.3.1", url: "https://example.test/app.dmg" });
  });

  it("returns null when the latest stable desktop release is not newer", () => {
    const update = findLatestUpdate(
      [
        { tag_name: "desktop-v0.3.1", html_url: "https://example.test/release/0.3.1" },
        { tag_name: "desktop-v0.3.0", html_url: "https://example.test/release/0.3.0" },
      ],
      "0.3.1",
    );

    expect(update).toBeNull();
  });

  it("falls back to the release page when no DMG asset is attached", () => {
    const update = findLatestUpdate(
      [{ tag_name: "desktop-v0.3.2", html_url: "https://example.test/release/0.3.2", assets: [] }],
      "0.3.1",
    );

    expect(update).toEqual({ version: "0.3.2", url: "https://example.test/release/0.3.2" });
  });
});
