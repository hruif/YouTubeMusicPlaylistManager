import { describe, it, expect } from "vitest";
import { bestYoutubeMatch, combineFromCache, parseYouTubePlaylistId } from "./ytmusic";
// These moved to the Electron main process (they operate on youtubei.js internals).
import { normalizeCookie, isPlaylistEditable } from "../../electron/yt";

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

describe("parseYouTubePlaylistId", () => {
  it("extracts list= from a YT Music URL", () => {
    expect(parseYouTubePlaylistId("https://music.youtube.com/playlist?list=PLabc1234567")).toBe("PLabc1234567");
  });
  it("extracts list= regardless of param position", () => {
    expect(parseYouTubePlaylistId("https://www.youtube.com/watch?v=xyz&list=PLabc1234567")).toBe("PLabc1234567");
  });
  it("strips the VL browse-id prefix", () => {
    expect(parseYouTubePlaylistId("https://music.youtube.com/playlist?list=VLPLabc1234567")).toBe("PLabc1234567");
  });
  it("accepts a bare id", () => {
    expect(parseYouTubePlaylistId("PLabc1234567")).toBe("PLabc1234567");
  });
  it("rejects junk / too-short ids", () => {
    expect(parseYouTubePlaylistId("not a playlist")).toBeNull();
    expect(parseYouTubePlaylistId("https://music.youtube.com/")).toBeNull();
    expect(parseYouTubePlaylistId("")).toBeNull();
  });
});

describe("normalizeCookie (SAPISID aliasing)", () => {
  it("leaves a cookie that already has SAPISID untouched", () => {
    const c = "FOO=1; SAPISID=abc; BAR=2";
    expect(normalizeCookie(c)).toBe(c);
  });
  it("adds SAPISID from __Secure-3PAPISID when missing", () => {
    expect(normalizeCookie("__Secure-3PAPISID=abc; X=1")).toBe("__Secure-3PAPISID=abc; X=1; SAPISID=abc");
  });
  it("does not treat __Secure-3PAPISID as a present SAPISID (boundary-anchored)", () => {
    expect(normalizeCookie("__Secure-3PAPISID=zzz")).toContain("; SAPISID=zzz");
  });
  it("leaves a cookie with neither unchanged", () => {
    expect(normalizeCookie("FOO=1; BAR=2")).toBe("FOO=1; BAR=2");
  });
});

describe("isPlaylistEditable (ownership detection)", () => {
  it("true via the legacy header.type fallback", () => {
    expect(isPlaylistEditable({ header: { type: "MusicEditablePlaylistDetailHeader" } })).toBe(true);
  });
  it("true when the editable node is in the page memo even though header is MusicResponsiveHeader", () => {
    const playlist = {
      header: { type: "MusicResponsiveHeader" },
      page: { contents_memo: { getType: () => [{}] } },
    };
    expect(isPlaylistEditable(playlist)).toBe(true);
  });
  it("false when neither the header nor the memo has the editable node", () => {
    const playlist = {
      header: { type: "MusicResponsiveHeader" },
      page: { contents_memo: { getType: () => [] } },
    };
    expect(isPlaylistEditable(playlist)).toBe(false);
  });
  it("false (no throw) when the page is absent", () => {
    expect(isPlaylistEditable({ header: { type: "MusicResponsiveHeader" } })).toBe(false);
  });
});
