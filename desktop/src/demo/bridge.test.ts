import { describe, expect, it, vi } from "vitest";
import { createDemoBackend } from "./bridge";
import { CACHE_VERSION } from "../lib/cache";
import { DEMO_SONGS } from "./data";

const song = (i: number) => DEMO_SONGS[i].videoId;

vi.useFakeTimers({ shouldAdvanceTime: true, advanceTimeDelta: 50 });

const ids = (r: unknown) => (r as { tracks: { videoId: string }[] }).tracks.map((t) => t.videoId);

describe("demo backend", () => {
  it("starts signed in with the demo library in the current cache format", async () => {
    const api = createDemoBackend();
    expect(await api.invoke("try_silent_sign_in")).toEqual({ cookie_names: ["SID"] });
    const cache = JSON.parse((await api.invoke("read_cache")) as string);
    expect(cache.version).toBe(CACHE_VERSION);
    expect(cache.shown).toHaveLength(6);
  });

  it("undo of a removal puts songs back in their original places", async () => {
    const api = createDemoBackend();
    const before = ids(await api.invoke("yt_get_playlist_tracks", { playlistId: "night" }));
    await api.invoke("yt_remove_videos", { playlistId: "night", videoIds: [before[1], before[2]] });
    expect(ids(await api.invoke("yt_get_playlist_tracks", { playlistId: "night" }))).toHaveLength(before.length - 2);
    await api.invoke("yt_restore_videos", {
      playlistId: "night",
      items: [
        { videoId: before[1], beforeVideoId: before[3] },
        { videoId: before[2], beforeVideoId: before[3] },
      ],
    });
    expect(ids(await api.invoke("yt_get_playlist_tracks", { playlistId: "night" }))).toEqual(before);
  });

  it("removes only the extra copies of repeated songs", async () => {
    const api = createDemoBackend();
    const before = ids(await api.invoke("yt_get_playlist_tracks", { playlistId: "gym" }));
    expect(await api.invoke("yt_remove_repeated_videos", { playlistId: "gym", videoIds: [song(5)] })).toBe(1);
    const after = ids(await api.invoke("yt_get_playlist_tracks", { playlistId: "gym" }));
    expect(after).toEqual(before.slice(0, -1)); // the first copy keeps its place
  });

  it("creates and deletes playlists, and keeps each demo separate", async () => {
    const api = createDemoBackend();
    const id = (await api.invoke("yt_create_playlist", { title: "Mine", videoIds: [song(1), song(2)] })) as string;
    expect(ids(await api.invoke("yt_get_playlist_tracks", { playlistId: id }))).toEqual([song(1), song(2)]);
    await api.invoke("yt_delete_playlist", { playlistId: id });
    await expect(api.invoke("yt_get_playlist_tracks", { playlistId: id })).rejects.toThrow("demo playlists");
    expect(await createDemoBackend().invoke("yt_get_library")).toHaveLength(6);
  });

  it("plays songs in YouTube Music, and playlists or queues as a temporary YouTube queue", async () => {
    const api = createDemoBackend();
    const opened: string[] = [];
    vi.stubGlobal("window", { open: (href: string) => opened.push(href) });
    await api.openExternal(`https://music.youtube.com/watch?v=${song(0)}`);
    // A queue opens as soon as it's created (inside the click), and isn't opened again after.
    const queue = (await api.invoke("yt_create_playlist", { title: "Queue", videoIds: [song(3), song(4)], privacy: "UNLISTED" })) as string;
    await api.openExternal(`https://music.youtube.com/playlist?list=${queue}`);
    // A demo playlist opened from its menu plays as a queue too.
    await api.openExternal("https://music.youtube.com/playlist?list=focus");
    await api.openExternal("https://music.youtube.com/watch?v=notADemoSong");
    await api.openExternal("https://github.com/hruif/YouTubeMusicPlaylistManager");
    expect(opened).toEqual([
      `https://music.youtube.com/watch?v=${song(0)}`,
      `https://www.youtube.com/watch_videos?video_ids=${song(3)},${song(4)}`,
      expect.stringMatching(/^https:\/\/www\.youtube\.com\/watch_videos\?video_ids=/),
      "https://github.com/hruif/YouTubeMusicPlaylistManager",
    ]);
    vi.unstubAllGlobals();
  });

  it("explains what the demo can't do", async () => {
    const api = createDemoBackend();
    await expect(api.invoke("proxy_http_request", {})).rejects.toThrow("Spotify isn't available in this demo");
    await expect(api.invoke("unknown_command")).rejects.toThrow("isn't available in this demo");
  });
});
