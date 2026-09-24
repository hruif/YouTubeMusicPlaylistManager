// Pure song-list logic, kept out of App so it can be unit-tested.

import type { CombinedSong, Track } from "./ytmusic";
import type { SongFilters, SortKey } from "./settings";
import { isUnavailableTitle } from "./format";

export type SongView = {
  query: string;
  filters: SongFilters;
  sortKey: SortKey;
  sortAsc: boolean;
  customNames: Record<string, string>;
};

// Search (title, artist, or your custom name), then filters, then sort. Never mutates `songs`.
export function visibleSongsFor(songs: CombinedSong[], v: SongView): CombinedSong[] {
  const q = v.query.trim().toLowerCase();
  let filtered = songs;
  if (q)
    filtered = filtered.filter(
      (s) =>
        s.title.toLowerCase().includes(q) ||
        s.artist.toLowerCase().includes(q) ||
        (v.customNames[s.videoId]?.toLowerCase().includes(q) ?? false),
    );
  if (v.filters.duplicates) filtered = filtered.filter((s) => s.playlists.length > 1);
  if (v.filters.unavailable) filtered = filtered.filter((s) => isUnavailableTitle(s.title));
  const copy = [...filtered];
  copy.sort((a, b) => {
    let cmp = 0;
    if (v.sortKey === "title") cmp = a.title.localeCompare(b.title);
    else if (v.sortKey === "artist") cmp = a.artist.localeCompare(b.artist);
    else if (v.sortKey === "album") cmp = (a.album ?? "").localeCompare(b.album ?? "");
    else if (v.sortKey === "duration") cmp = (a.duration ?? 0) - (b.duration ?? 0);
    else cmp = a.playlists.length - b.playlists.length;
    return v.sortAsc ? cmp : -cmp;
  });
  return copy;
}

// Undo of a removal: for each removed song (in playlist order), the song that followed it before
// the removal and is still there, so it can go back in front of it. null = it was at the end.
// Songs not found in `before` are skipped.
export function planRestore(
  videoIds: string[],
  before: Track[],
): { videoId: string; beforeVideoId: string | null }[] {
  const removed = new Set(videoIds);
  return videoIds
    .map((videoId) => ({ videoId, index: before.findIndex((t) => t.videoId === videoId) }))
    .filter((i) => i.index >= 0)
    .sort((a, b) => a.index - b.index)
    .map(({ videoId, index }) => ({
      videoId,
      beforeVideoId: before.slice(index + 1).find((t) => !removed.has(t.videoId))?.videoId ?? null,
    }));
}
