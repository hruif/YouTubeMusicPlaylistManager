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

  it("surfaces the zipped-.app asset for the in-place updater (alongside the dmg)", () => {
    const update = findLatestUpdate(
      [
        {
          tag_name: "desktop-v0.4.0",
          html_url: "https://example.test/release/0.4.0",
          assets: [
            { name: "YouTube.Music.Manager-0.4.0-universal.dmg", browser_download_url: "https://example.test/app.dmg" },
            { name: "YouTube.Music.Manager-0.4.0-universal-mac.zip", browser_download_url: "https://example.test/app.zip" },
          ],
        },
      ],
      "0.3.3",
    );

    expect(update).toEqual({ version: "0.4.0", url: "https://example.test/app.dmg", zipUrl: "https://example.test/app.zip" });
  });

  it("selects the highest stable version even when releases are unsorted", () => {
    const update = findLatestUpdate(
      [
        { tag_name: "desktop-v0.9.9", html_url: "https://example.test/0.9.9" },
        { tag_name: "desktop-v0.10.0", html_url: "https://example.test/0.10.0" },
        { tag_name: "desktop-v0.8.0", html_url: "https://example.test/0.8.0" },
      ],
      "0.9.0",
    );

    expect(update).toEqual({ version: "0.10.0", url: "https://example.test/0.10.0" });
  });

  it("ignores drafts, malformed tags, and unrelated release families", () => {
    expect(findLatestUpdate(
      [
        { tag_name: "desktop-v9.0.0", draft: true, html_url: "https://example.test/draft" },
        { tag_name: "desktop-vnot-a-version", html_url: "https://example.test/malformed" },
        { tag_name: "v9.0.0", html_url: "https://example.test/python" },
      ],
      "1.0.0",
    )).toBeNull();
  });
});
