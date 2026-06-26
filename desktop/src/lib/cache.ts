// Local library cache: the playlist list + each playlist's tracks, persisted as JSON in the app
// data dir (via the Rust read_cache/write_cache commands). Lets the app load instantly and fetch
// only on an explicit update. It's all text, so size is negligible.

import { invoke } from "./native";
import type { Playlist, Track } from "./ytmusic";

// A locally-archived deleted playlist, so an accidental delete doesn't lose the song list — it
// can be recreated. (YouTube's delete is permanent and has no undo.)
export type DeletedPlaylist = { id: string; title: string; tracks: Track[]; deletedAt: number };

// Cache schema version. Bump when a change to how tracks are parsed/stored means existing cached
// data must be re-fetched to be correct (old parsed rows can't be transformed in place — they have
// to be re-pulled with the current parser). loadCache() drops the cached tracks on any upgrade.
// History: v1 forces a re-fetch so the 0.3.1 artist-fallback parse reaches caches written earlier.
export const CACHE_VERSION = 1;

export type LibraryCache = {
  version: number;
  playlists: Playlist[];
  tracksByPlaylist: Record<string, Track[]>;
  updatedAt: Record<string, number>; // playlist id -> last-fetched epoch ms
  shown: string[]; // playlist ids the user has added to the sidebar (opt-in; empty = none shown)
  external: string[]; // playlist ids added by URL (not in your library) — preserved across refresh
  editable: string[]; // playlist ids you own (detected on update)
  deleted: DeletedPlaylist[]; // archive of deleted playlists (for recreation)
  unmatched: Record<string, { title: string; artist: string }[]>; // Spotify tracks not matched, by new playlist id
  customNames: Record<string, string>; // local searchable aliases, by videoId
  removedSongs: Record<string, { videoId?: string; title: string; artist: string; removedAt: number }[]>; // archived on update/removal, by playlist id
  tempPlaylists: { id: string; title: string; createdAt: number }[]; // "play in YouTube Music" queues, for cleanup
};

export const EMPTY_CACHE: LibraryCache = {
  version: CACHE_VERSION,
  playlists: [],
  tracksByPlaylist: {},
  updatedAt: {},
  shown: [],
  external: [],
  editable: [],
  deleted: [],
  unmatched: {},
  customNames: {},
  removedSongs: {},
  tempPlaylists: [],
};

// Returns the cache plus whether an upgrade migration ran, so the app can force a one-time refresh
// after an update even if the user disabled auto-refresh-on-launch.
export async function loadCache(): Promise<{ cache: LibraryCache; migrated: boolean }> {
  const raw = await invoke<string | null>("read_cache");
  if (!raw) return { cache: { ...EMPTY_CACHE }, migrated: false };
  try {
    const parsed = JSON.parse(raw) as Partial<LibraryCache>;
    const cache: LibraryCache = {
      version: CACHE_VERSION,
      playlists: parsed.playlists ?? [],
      tracksByPlaylist: parsed.tracksByPlaylist ?? {},
      updatedAt: parsed.updatedAt ?? {},
      shown: parsed.shown ?? [],
      external: parsed.external ?? [],
      editable: parsed.editable ?? [],
      deleted: parsed.deleted ?? [],
      unmatched: parsed.unmatched ?? {},
      customNames: parsed.customNames ?? {},
      removedSongs: parsed.removedSongs ?? {},
      tempPlaylists: parsed.tempPlaylists ?? [],
    };
    // Schema upgrade: drop cached tracks so they're re-fetched with the current parser. The stored
    // rows reflect whatever parser wrote them, so an improved parse (e.g. the 0.3.1 artist fallback)
    // can only reach them via a re-fetch. Keyed metadata (custom names, removed/unmatched archives,
    // deleted playlists, sidebar selection) is schema-stable and preserved. One-time, post-update.
    const prevVersion = parsed.version ?? 0;
    const migrated = prevVersion < CACHE_VERSION;
    if (migrated) {
      cache.tracksByPlaylist = {};
      cache.updatedAt = {};
    }
    return { cache, migrated };
  } catch {
    return { cache: { ...EMPTY_CACHE }, migrated: false };
  }
}

export async function saveCache(cache: LibraryCache): Promise<void> {
  await invoke("write_cache", { contents: JSON.stringify(cache) });
}
