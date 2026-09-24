import { describe, expect, it } from "vitest";
import { planRestore, visibleSongsFor, type SongView } from "./songs";
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
  filters: { duplicates: false, unavailable: false },
  sortKey: "title",
  sortAsc: true,
  customNames: {},
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
    expect(ids(visibleSongsFor(songs, view({ filters: { duplicates: true, unavailable: false } })))).toEqual(["a"]);
    expect(ids(visibleSongsFor(songs, view({ filters: { duplicates: false, unavailable: true } })))).toEqual(["c"]);
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
