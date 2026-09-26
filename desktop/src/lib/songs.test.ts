import { describe, expect, it } from "vitest";
import { planRestore, repeatedWithinPlaylists, visibleSongsFor, type SongView } from "./songs";
import { NO_FILTERS } from "./settings";
import type { CombinedSong, Track } from "./ytmusic";

const song = (videoId: string, title: string, extra: Partial<CombinedSong> = {}): CombinedSong => ({
  videoId,
  title,
  artist: "",
  playlists: ["P"],
  ...extra,
});
const view = (v: Partial<SongView> = {}): SongView => ({
  query: "",
  filters: NO_FILTERS,
  sortKey: "title",
  sortAsc: true,
  customNames: {},
  playlistCount: 1,
  repeated: new Set(),
  ...v,
});
const ids = (s: CombinedSong[]) => s.map((x) => x.videoId);

describe("visibleSongsFor", () => {
  const songs = [
    song("a", "Beta", { artist: "Zed", album: "Alpha", duration: 300, playlists: ["P", "Q"] }),
    song("b", "Alpha", { artist: "Yan", album: "Gamma", duration: 100 }),
    song("c", "[Deleted video]", { artist: "Xi", duration: 200 }),
  ];

  it("searches title, artist, and custom names, case-insensitively", () => {
    expect(ids(visibleSongsFor(songs, view({ query: "alp" })))).toEqual(["b"]);
    expect(ids(visibleSongsFor(songs, view({ query: "ZED" })))).toEqual(["a"]);
    expect(ids(visibleSongsFor(songs, view({ query: "gym tune", customNames: { c: "Gym tune" } })))).toEqual(["c"]);
  });

  it("applies the duplicates and unavailable filters", () => {
    expect(ids(visibleSongsFor(songs, view({ filters: { ...NO_FILTERS, duplicates: true } })))).toEqual(["a"]);
    expect(ids(visibleSongsFor(songs, view({ filters: { ...NO_FILTERS, unavailable: true } })))).toEqual(["c"]);
  });

  it("\"in every selected playlist\" keeps only songs all selected playlists share", () => {
    expect(ids(visibleSongsFor(songs, view({ filters: { ...NO_FILTERS, inAll: true }, playlistCount: 2 })))).toEqual(["a"]);
    expect(visibleSongsFor(songs, view({ filters: { ...NO_FILTERS, inAll: true }, playlistCount: 3 }))).toEqual([]);
  });

  it("\"repeated within a playlist\" keeps songs listed more than once in one playlist", () => {
    const repeated = new Set(["b"]);
    expect(ids(visibleSongsFor(songs, view({ filters: { ...NO_FILTERS, repeated: true }, repeated })))).toEqual(["b"]);
  });

  it("sorts by each column, both directions, with missing album/duration first", () => {
    expect(ids(visibleSongsFor(songs, view({ sortKey: "album" })))).toEqual(["c", "a", "b"]);
    expect(ids(visibleSongsFor(songs, view({ sortKey: "duration" })))).toEqual(["b", "c", "a"]);
    expect(ids(visibleSongsFor(songs, view({ sortKey: "duration", sortAsc: false })))).toEqual(["a", "c", "b"]);
    expect(ids(visibleSongsFor(songs, view({ sortKey: "count", sortAsc: false })))[0]).toBe("a");
  });

  it("doesn't mutate its input", () => {
    const copy = [...songs];
    visibleSongsFor(songs, view({ sortKey: "duration" }));
    expect(songs).toEqual(copy);
  });
});

describe("repeatedWithinPlaylists", () => {
  const t = (videoId: string): Track => ({ videoId, title: videoId, artist: "" });
  it("finds songs repeated inside one playlist, not songs merely shared between playlists", () => {
    const playlists = [{ id: "p", title: "P" }, { id: "q", title: "Q" }];
    const tracks = { p: [t("a"), t("b"), t("a")], q: [t("b"), t("c")] };
    expect([...repeatedWithinPlaylists(playlists, tracks)]).toEqual(["a"]);
  });
});

describe("planRestore", () => {
  const t = (videoId: string): Track => ({ videoId, title: videoId, artist: "" });
  const before = ["A", "B", "C", "D", "E"].map(t);

  it("puts each song back in front of the next song that wasn't removed", () => {
    expect(planRestore(["B", "C"], before)).toEqual([
      { videoId: "B", beforeVideoId: "D" },
      { videoId: "C", beforeVideoId: "D" },
    ]);
  });

  it("orders the plan by playlist position, not selection order", () => {
    expect(planRestore(["D", "A"], before).map((i) => i.videoId)).toEqual(["A", "D"]);
  });

  it("uses null for songs that were at the end", () => {
    expect(planRestore(["D", "E"], before)).toEqual([
      { videoId: "D", beforeVideoId: null },
      { videoId: "E", beforeVideoId: null },
    ]);
  });

  it("skips songs that weren't in the playlist", () => {
    expect(planRestore(["Z"], before)).toEqual([]);
  });
});
