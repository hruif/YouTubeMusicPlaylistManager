// Pure song-list logic, kept out of App so it can be unit-tested.

import type { CombinedSong, Playlist, Track } from "./ytmusic";
import type { SongFilters, SortKey } from "./settings";
import { isUnavailableTitle } from "./format";

export type SongView = {
  query: string;
  filters: SongFilters;
  sortKey: SortKey;
  sortAsc: boolean;
  customNames: Record<string, string>;
  playlistCount: number; // how many playlists are selected (for "in every selected playlist")
  repeated: Set<string>; // videoIds that appear more than once within a single selected playlist
  order?: Map<string, number>; // a shuffle: position by videoId, used instead of the column sort
};

// A random order for the given songs (see SongView.order).
export function shuffleOrder(videoIds: string[], random: () => number = Math.random): Map<string, number> {
  return new Map(shuffled(videoIds, random).map((id, i) => [id, i]));
}

// Songs listed more than once within the same playlist (the view shows each song once, so repeats
// are otherwise invisible).
export function repeatedWithinPlaylists(playlists: Playlist[], tracksByPlaylist: Record<string, Track[]>): Set<string> {
  const repeated = new Set<string>();
  for (const p of playlists) {
    const seen = new Set<string>();
    for (const t of tracksByPlaylist[p.id] ?? []) {
      if (seen.has(t.videoId)) repeated.add(t.videoId);
      else seen.add(t.videoId);
    }
  }
  return repeated;
}

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
  if (v.filters.inAll) filtered = filtered.filter((s) => s.playlists.length >= v.playlistCount);
  if (v.filters.repeated) filtered = filtered.filter((s) => v.repeated.has(s.videoId));
  if (v.filters.unavailable) filtered = filtered.filter((s) => isUnavailableTitle(s.title));
  const copy = [...filtered];
  if (v.order) {
    // Songs that arrived after the shuffle (e.g. a playlist was added) go at the end.
    const at = (s: CombinedSong) => v.order!.get(s.videoId) ?? Number.MAX_SAFE_INTEGER;
    return copy.sort((a, b) => at(a) - at(b));
  }
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

// A shuffled copy (Fisher–Yates), for "Shuffle": every order equally likely.
export function shuffled<T>(items: T[], random: () => number = Math.random): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
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
