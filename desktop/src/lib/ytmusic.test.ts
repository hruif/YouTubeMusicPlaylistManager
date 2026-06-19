import { describe, it, expect } from "vitest";
import { bestYoutubeMatch, combineFromCache } from "./ytmusic";

const cand = (videoId: string, title: string, artist: string) => ({ videoId, title, artist });

describe("bestYoutubeMatch (conservative Spotify→YT matcher)", () => {
  it("matches when one title's tokens ⊆ the other and an artist word overlaps", () => {
    const c = [cand("v1", "Some Song (feat. X)", "Artist One")];
    expect(bestYoutubeMatch(c, "Some Song", "Artist One")?.videoId).toBe("v1");
  });
  it("is case- and punctuation-insensitive (note: NOT diacritic-insensitive, matching the Python app)", () => {
    const c = [cand("v1", "Some Song!!!", "Artist One")];
    expect(bestYoutubeMatch(c, "some song", "artist one")?.videoId).toBe("v1");
  });
  it("rejects when no artist word overlaps", () => {
    const c = [cand("v1", "Some Song", "Adele")];
    expect(bestYoutubeMatch(c, "Some Song", "Beyonce")).toBeNull();
  });
  it("rejects when neither title is a subset of the other", () => {
    const c = [cand("v1", "Totally Other Track", "Artist One")];
    expect(bestYoutubeMatch(c, "Some Song", "Artist One")).toBeNull();
  });
  it("accepts on the title alone when the source has no artist", () => {
    const c = [cand("v1", "Some Song", "Whoever")];
    expect(bestYoutubeMatch(c, "Some Song", "")?.videoId).toBe("v1");
  });
  it("returns the first confident candidate (results are relevance-ranked)", () => {
    const c = [cand("v1", "Wrong One", "Artist One"), cand("v2", "Some Song", "Artist One")];
    expect(bestYoutubeMatch(c, "Some Song", "Artist One")?.videoId).toBe("v2");
  });
});

describe("combineFromCache", () => {
  const t = (videoId: string) => ({ videoId, title: "t", artist: "a" });
  it("dedupes by videoId and records each playlist a song appears in", () => {
    const selected = [
      { id: "A", title: "PA" },
      { id: "B", title: "PB" },
    ];
    const byPlaylist = { A: [t("x"), t("y")], B: [t("x"), t("z")] };
    const out = combineFromCache(selected, byPlaylist);
    expect(out).toHaveLength(3);
    expect(out.find((s) => s.videoId === "x")?.playlists.sort()).toEqual(["PA", "PB"]);
    expect(out.find((s) => s.videoId === "y")?.playlists).toEqual(["PA"]);
  });
  it("ignores selected playlists with no cached tracks", () => {
    expect(combineFromCache([{ id: "A", title: "PA" }], {})).toEqual([]);
  });
});
