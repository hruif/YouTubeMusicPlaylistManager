import { describe, it, expect } from "vitest";
import { applyFetchedPlaylistTitles, bestYoutubeMatch, combineFromCache, parseYouTubePlaylistId } from "./ytmusic";
// These moved to the Electron main process (they operate on youtubei.js internals).
import { normalizeCookie, isPlaylistEditable, extractTrackFromPlaylistItem } from "../../electron/yt";

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
  it("can calculate membership from a broader playlist scope without adding its songs", () => {
    const selected = [{ id: "A", title: "Selected" }];
    const sidebar = [
      ...selected,
      { id: "B", title: "Also here" },
      { id: "C", title: "Unrelated" },
    ];
    const byPlaylist = {
      A: [t("shared"), t("selected-only")],
      B: [t("shared"), t("sidebar-only")],
      C: [t("other")],
    };

    const out = combineFromCache(selected, byPlaylist, sidebar);
    expect(out.map((s) => s.videoId).sort()).toEqual(["selected-only", "shared"]);
    expect(out.find((s) => s.videoId === "shared")?.playlists).toEqual(["Selected", "Also here"]);
    expect(out.find((s) => s.videoId === "selected-only")?.playlists).toEqual(["Selected"]);
  });
  it("always includes selected-playlist membership when the extra scope omits it", () => {
    const selected = [{ id: "A", title: "Selected" }];
    const out = combineFromCache(selected, { A: [t("x")] }, []);
    expect(out[0].playlists).toEqual(["Selected"]);
  });
});

describe("applyFetchedPlaylistTitles", () => {
  it("updates renamed playlists and leaves playlists without a fetched title unchanged", () => {
    const playlists = [
      { id: "A", title: "Old name" },
      { id: "B", title: "Keep me" },
    ];
    expect(applyFetchedPlaylistTitles(playlists, { A: "New name" })).toEqual([
      { id: "A", title: "New name" },
      { id: "B", title: "Keep me" },
    ]);
  });

  it("ignores blank fetched titles", () => {
    expect(applyFetchedPlaylistTitles([{ id: "A", title: "Known" }], { A: "  " })).toEqual([
      { id: "A", title: "Known" },
    ]);
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
  it("true when the raw response contains an editable playlist header renderer", () => {
    expect(isPlaylistEditable({ contents: [{ musicEditablePlaylistDetailHeaderRenderer: {} }] })).toBe(true);
  });
});

describe("extractTrackFromPlaylistItem", () => {
  it("uses authors when youtubei.js does not expose artists", () => {
    const track = extractTrackFromPlaylistItem({
      id: "QQC4PKXIWyA",
      title: "アンノウン・マザーグース　歌ってみた－遊",
      authors: [{ name: "Yuu Miyashita" }],
    });
    expect(track).toMatchObject({
      videoId: "QQC4PKXIWyA",
      title: "アンノウン・マザーグース　歌ってみた－遊",
      artist: "Yuu Miyashita",
    });
  });

  it("falls back to the second flex column for song artists", () => {
    const track = extractTrackFromPlaylistItem({
      title: { text: "Theme Of Bayonetta 2 - Tomorrow Is Mine", endpoint: { payload: { videoId: "ScUZhX9mVEk" } } },
      artists: [],
      flex_columns: [
        { title: { text: "Theme Of Bayonetta 2 - Tomorrow Is Mine" } },
        { title: { text: "Keeley Bumford" } },
      ],
    });
    expect(track).toMatchObject({
      videoId: "ScUZhX9mVEk",
      title: "Theme Of Bayonetta 2 - Tomorrow Is Mine",
      artist: "Keeley Bumford",
    });
  });

  it("extracts raw browse rows before youtubei.js drops ids from unknown item types", () => {
    const track = extractTrackFromPlaylistItem({
      musicResponsiveListItemRenderer: {
        flexColumns: [
          {
            musicResponsiveListItemFlexColumnRenderer: {
              text: {
                runs: [
                  {
                    text: "Simple And Clean",
                    navigationEndpoint: { watchEndpoint: { videoId: "B1nDzB1P8GM" } },
                  },
                ],
              },
            },
          },
          {
            musicResponsiveListItemFlexColumnRenderer: {
              text: { runs: [{ text: "Hikaru Utada" }] },
            },
          },
        ],
      },
    });
    expect(track).toMatchObject({
      videoId: "B1nDzB1P8GM",
      title: "Simple And Clean",
      artist: "Hikaru Utada",
    });
  });
});
