import { describe, it, expect } from "vitest";
import { formatPlaylistNames, isUnavailableTitle, relativeAge } from "./format";

describe("isUnavailableTitle", () => {
  it("flags deleted/private/unavailable/restricted placeholders", () => {
    expect(isUnavailableTitle("[Deleted video]")).toBe(true);
    expect(isUnavailableTitle("[Private video]")).toBe(true);
    expect(isUnavailableTitle("[Unavailable]")).toBe(true);
    expect(isUnavailableTitle("[Restricted video]")).toBe(true);
  });
  it("does not flag a normal title", () => {
    expect(isUnavailableTitle("Bohemian Rhapsody")).toBe(false);
    expect(isUnavailableTitle("[Live] at Wembley")).toBe(false); // not a placeholder keyword
  });
});

describe("relativeAge", () => {
  it("returns 'never' for undefined", () => {
    expect(relativeAge(undefined)).toBe("never");
  });
  it("returns 'just now' for the current moment", () => {
    expect(relativeAge(Date.now())).toBe("just now");
  });
  it("formats minutes / hours / days", () => {
    expect(relativeAge(Date.now() - 5 * 60_000)).toBe("5m ago");
    expect(relativeAge(Date.now() - 3 * 3_600_000)).toBe("3h ago");
    expect(relativeAge(Date.now() - 2 * 86_400_000)).toBe("2d ago");
  });
});

describe("formatPlaylistNames", () => {
  it("shows up to two playlist names", () => {
    expect(formatPlaylistNames(["Favorites"])).toBe("Favorites");
    expect(formatPlaylistNames(["Favorites", "Road trip"])).toBe("Favorites, Road trip");
  });

  it("summarizes additional playlists", () => {
    expect(formatPlaylistNames(["A", "B", "C", "D", "E"])).toBe("A, B (+3 more)");
  });

  it("handles an empty membership defensively", () => {
    expect(formatPlaylistNames([])).toBe("None");
  });
});
