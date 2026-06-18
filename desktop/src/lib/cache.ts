// Local library cache: the playlist list + each playlist's tracks, persisted as JSON in the app
// data dir (via the Rust read_cache/write_cache commands). Lets the app load instantly and fetch
// only on an explicit update. It's all text, so size is negligible.

import { invoke } from "@tauri-apps/api/core";
import type { Playlist, Track } from "./ytmusic";

// A locally-archived deleted playlist, so an accidental delete doesn't lose the song list — it
// can be recreated. (YouTube's delete is permanent and has no undo.)
export type DeletedPlaylist = { id: string; title: string; tracks: Track[]; deletedAt: number };

export type LibraryCache = {
  playlists: Playlist[];
  tracksByPlaylist: Record<string, Track[]>;
  updatedAt: Record<string, number>; // playlist id -> last-fetched epoch ms
  hidden: string[]; // playlist ids hidden from the main sidebar
  editable: string[]; // playlist ids you own (detected on update)
  deleted: DeletedPlaylist[]; // archive of deleted playlists (for recreation)
  unmatched: Record<string, { title: string; artist: string }[]>; // Spotify tracks not matched, by new playlist id
};

export const EMPTY_CACHE: LibraryCache = {
  playlists: [],
  tracksByPlaylist: {},
  updatedAt: {},
  hidden: [],
  editable: [],
  deleted: [],
  unmatched: {},
};

export async function loadCache(): Promise<LibraryCache> {
  const raw = await invoke<string | null>("read_cache");
  if (!raw) return { ...EMPTY_CACHE };
  try {
    const parsed = JSON.parse(raw) as Partial<LibraryCache>;
    return {
      playlists: parsed.playlists ?? [],
      tracksByPlaylist: parsed.tracksByPlaylist ?? {},
      updatedAt: parsed.updatedAt ?? {},
      hidden: parsed.hidden ?? [],
      editable: parsed.editable ?? [],
      deleted: parsed.deleted ?? [],
      unmatched: parsed.unmatched ?? {},
    };
  } catch {
    return { ...EMPTY_CACHE };
  }
}

export async function saveCache(cache: LibraryCache): Promise<void> {
  await invoke("write_cache", { contents: JSON.stringify(cache) });
}
