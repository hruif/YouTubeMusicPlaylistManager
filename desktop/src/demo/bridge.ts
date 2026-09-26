// A pretend Electron backend for the live demo on the website: the real app UI runs against an
// in-memory copy of the demo library, so every edit (remove, undo, new playlist, remove repeats)
// really happens, and a reload starts over. Edits never reach YouTube Music; only playing does,
// by opening the songs there.

import type { Playlist, Track } from "../lib/ytmusic";
import { CACHE_VERSION } from "../lib/cacheVersion"; // not ../lib/cache: that loads ../lib/native too early
import { DEMO_PLAYLISTS, DEMO_SONGS, DEMO_TRACKS } from "./data";

type Args = Record<string, unknown>;

export function createDemoBackend() {
  const catalog = new Map(DEMO_SONGS.map((t) => [t.videoId, t]));
  let playlists: Playlist[] = DEMO_PLAYLISTS.map((p) => ({ ...p }));
  const tracks: Record<string, Track[]> = Object.fromEntries(Object.entries(DEMO_TRACKS).map(([id, t]) => [id, [...t]]));
  let signedIn = true;
  let created = 0;
  const openedQueues = new Set<string>();
  const openInNewTab = (href: string) => window.open(href, "_blank", "noopener");
  const queueUrl = (videoIds: string[]) =>
    `https://www.youtube.com/watch_videos?video_ids=${[...new Set(videoIds)].slice(0, 50).join(",")}`;
  const progressListeners = new Set<(p: { playlistId: string; loaded: number; total?: number }) => void>();
  const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));
  const listOf = (playlistId: unknown) => {
    const id = String(playlistId);
    if (!tracks[id]) throw new Error("Only the demo playlists are available in this demo.");
    return tracks[id];
  };

  const commands: Record<string, (a: Args) => unknown> = {
    read_cache: () =>
      JSON.stringify({
        version: CACHE_VERSION,
        playlists,
        tracksByPlaylist: tracks,
        updatedAt: Object.fromEntries(playlists.map((p) => [p.id, Date.now() - 3600e3])),
        shown: playlists.map((p) => p.id),
        editable: playlists.map((p) => p.id),
      }),
    write_cache: () => null,
    try_silent_sign_in: () => (signedIn ? { cookie_names: ["SID"] } : null),
    sign_in_youtube_music: async () => {
      await pause(600);
      signedIn = true;
      return { cookie_names: ["SID"] };
    },
    sign_out_youtube_music: () => {
      signedIn = false;
      return null;
    },
    yt_account_info: () => ({ name: "Demo" }),
    yt_get_library: async () => {
      await pause(300);
      return playlists;
    },
    // Loads in two "pages" so the sidebar's loading pies have something to show.
    yt_get_playlist_tracks: async (a) => {
      const list = listOf(a.playlistId);
      const playlistId = String(a.playlistId);
      for (const loaded of [Math.ceil(list.length / 2), list.length]) {
        await pause(250);
        progressListeners.forEach((l) => l({ playlistId, loaded, total: list.length }));
      }
      return { tracks: [...list], editable: true, title: playlists.find((p) => p.id === playlistId)?.title ?? "" };
    },
    yt_add_videos: async (a) => {
      await pause(300);
      const list = listOf(a.playlistId);
      for (const id of a.videoIds as string[]) {
        const t = catalog.get(id);
        if (t) list.push(t);
      }
      return null;
    },
    // Removes one copy of each song, like the real backend; returns the ones it found.
    yt_remove_videos: async (a) => {
      await pause(300);
      const list = listOf(a.playlistId);
      const removed: string[] = [];
      for (const id of a.videoIds as string[]) {
        const at = list.findIndex((t) => t.videoId === id);
        if (at >= 0) {
          list.splice(at, 1);
          removed.push(id);
        }
      }
      return removed;
    },
    yt_remove_repeated_videos: async (a) => {
      await pause(300);
      const list = listOf(a.playlistId);
      const wanted = new Set(a.videoIds as string[]);
      const seen = new Set<string>();
      const kept = list.filter((t) => {
        if (!wanted.has(t.videoId)) return true;
        if (seen.has(t.videoId)) return false;
        seen.add(t.videoId);
        return true;
      });
      const count = list.length - kept.length;
      list.splice(0, list.length, ...kept);
      return count;
    },
    // Undo of a removal: each song goes back in front of the song that followed it.
    yt_restore_videos: async (a) => {
      await pause(400);
      const list = listOf(a.playlistId);
      for (const { videoId, beforeVideoId } of a.items as { videoId: string; beforeVideoId: string | null }[]) {
        const t = catalog.get(videoId);
        if (!t) continue;
        const at = beforeVideoId ? list.findIndex((x) => x.videoId === beforeVideoId) : -1;
        if (at >= 0) list.splice(at, 0, t);
        else list.push(t);
      }
      return true;
    },
    // A queue ("Play in YouTube Music") is the only kind created with a privacy setting. Open it now,
    // while still inside the click: the app opens queues after a short wait, and browsers block
    // new tabs that don't come straight from a click.
    yt_create_playlist: async (a) => {
      const id = `demo-playlist-${++created}`;
      if (a.privacy) {
        openInNewTab(queueUrl(a.videoIds as string[]));
        openedQueues.add(id);
      }
      await pause(400);
      playlists = [{ id, title: String(a.title) }, ...playlists];
      tracks[id] = (a.videoIds as string[]).map((v) => catalog.get(v)).filter((t): t is Track => !!t);
      return id;
    },
    yt_delete_playlist: async (a) => {
      await pause(300);
      playlists = playlists.filter((p) => p.id !== a.playlistId);
      delete tracks[String(a.playlistId)];
      return null;
    },
    yt_search: () => [],
    proxy_http_request: () => {
      throw new Error("Importing from Spotify isn't available in this demo.");
    },
    // CSV export saves a real file through the browser.
    export_text_file: (a) => {
      const url = URL.createObjectURL(new Blob([String(a.contents)], { type: "text/csv" }));
      const link = Object.assign(document.createElement("a"), { href: url, download: String(a.defaultName) });
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return true;
    },
  };

  return {
    isElectron: true as const,
    invoke: async (cmd: string, args: Args = {}) => {
      const handler = commands[cmd];
      if (!handler) throw new Error(`"${cmd}" isn't available in this demo.`);
      return handler(args);
    },
    onTracksProgress: (cb: (p: { playlistId: string; loaded: number; total?: number }) => void) => {
      progressListeners.add(cb);
      return () => progressListeners.delete(cb);
    },
    // Songs open in YouTube Music. A demo playlist or queue isn't on anyone's account, so it opens as
    // a temporary YouTube queue of its songs (watch_videos, up to 50; YouTube Music has no
    // equivalent link). Other YouTube links go nowhere; everything else opens in a new tab.
    openExternal: async (url: string) => {
      const u = new URL(url);
      if (!/(^|\.)youtube\.com$/.test(u.hostname)) return void openInNewTab(url);
      const song = u.searchParams.get("v");
      if (song && catalog.has(song)) return void openInNewTab(`https://music.youtube.com/watch?v=${song}`);
      const list = u.searchParams.get("list");
      if (!list || openedQueues.has(list) || !tracks[list]?.length) return;
      openInNewTab(queueUrl(tracks[list].map((t) => t.videoId)));
    },
    showWindow: async () => {},
    setBackgroundColor: async () => {},
    allowCloseAndQuit: async () => {},
    deferClose: async () => {},
    onCloseRequested: () => () => {},
    installUpdate: async () => false,
    onUpdateProgress: () => () => {},
  };
}
