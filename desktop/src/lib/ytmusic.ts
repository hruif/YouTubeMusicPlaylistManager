// YouTube Music client (renderer side). The actual youtubei.js work runs in the Electron main
// process; here the operations are thin IPC calls via the platform bridge. Pure helpers (the
// Spotify→YT matcher, combineFromCache, id parsing) stay here since they need no backend.

import { invoke } from "./native";

export type Playlist = { id: string; title: string };
export type Track = { videoId: string; title: string; artist: string; thumb?: string };
export type CombinedSong = Track & { playlists: string[] };
export type MatchCandidate = { videoId: string; title: string; artist: string };

type SignInResult = { cookie_names: string[] };

/** Interactive sign-in (opens the login window in main). Returns captured cookie names. */
export async function signIn(): Promise<string[]> {
  const r = await invoke<SignInResult>("sign_in_youtube_music");
  return r.cookie_names;
}

/** Startup auto sign-in from the persisted session. Returns names, or null if signed out. */
export async function trySilentSignIn(): Promise<string[] | null> {
  const r = await invoke<SignInResult | null>("try_silent_sign_in");
  return r ? r.cookie_names : null;
}

export async function signOut(): Promise<void> {
  await invoke("sign_out_youtube_music");
}

export async function getAccountInfo(): Promise<string> {
  return invoke<string>("yt_account_info");
}

export async function getLibraryPlaylists(): Promise<Playlist[]> {
  return invoke<Playlist[]>("yt_get_library");
}

export async function getPlaylistTracks(
  playlistId: string,
): Promise<{ tracks: Track[]; editable: boolean; title: string }> {
  return invoke("yt_get_playlist_tracks", { playlistId });
}

export async function addVideos(playlistId: string, videoIds: string[]): Promise<void> {
  await invoke("yt_add_videos", { playlistId, videoIds });
}

/** Returns the videoIds actually removed (some may be skipped if not found in the playlist). */
export async function removeVideos(playlistId: string, videoIds: string[]): Promise<string[]> {
  return invoke<string[]>("yt_remove_videos", { playlistId, videoIds });
}

export async function createPlaylist(title: string, videoIds: string[]): Promise<string | undefined> {
  return (await invoke<string | null>("yt_create_playlist", { title, videoIds })) ?? undefined;
}

export async function deletePlaylist(playlistId: string): Promise<void> {
  await invoke("yt_delete_playlist", { playlistId });
}

export async function searchYouTubeMusicSongs(query: string): Promise<MatchCandidate[]> {
  return invoke<MatchCandidate[]>("yt_search", { query });
}

// Parse a YouTube / YouTube Music playlist id from a URL or raw id (strips the VL browse prefix).
export function parseYouTubePlaylistId(input: string): string | null {
  const m = input.match(/[?&]list=([A-Za-z0-9_-]+)/) || input.match(/playlist\/([A-Za-z0-9_-]+)/);
  const raw = m ? m[1] : input.trim();
  if (!raw) return null;
  const id = raw.replace(/^VL/, "");
  return /^[A-Za-z0-9_-]{10,}$/.test(id) ? id : null;
}

/**
 * Fetch tracks for many playlists with bounded concurrency, tolerating per-playlist failures
 * (returned in `failures`) so one transient error doesn't abort the whole update.
 */
export async function fetchTracksForPlaylists(
  playlists: Playlist[],
  concurrency = 4,
  onDone?: (done: number, total: number, playlist: Playlist, ok: boolean) => void,
): Promise<{
  tracksByPlaylist: Record<string, Track[]>;
  editableIds: string[];
  notFoundIds: string[];
  failures: Playlist[];
}> {
  const tracksByPlaylist: Record<string, Track[]> = {};
  const editableIds: string[] = [];
  const notFoundIds: string[] = []; // playlists YouTube reports as gone (HTTP 404)
  const failures: Playlist[] = [];
  let next = 0;
  let done = 0;
  const worker = async (): Promise<void> => {
    while (next < playlists.length) {
      const playlist = playlists[next++];
      try {
        const { tracks, editable } = await getPlaylistTracks(playlist.id);
        tracksByPlaylist[playlist.id] = tracks;
        if (editable) editableIds.push(playlist.id);
        onDone?.(++done, playlists.length, playlist, true);
      } catch (err) {
        // Only treat an explicit 404 as "gone" — never an empty result or a transient error.
        const msg = err instanceof Error ? err.message : String(err);
        if (/status code 404/i.test(msg)) notFoundIds.push(playlist.id);
        else failures.push(playlist);
        onDone?.(++done, playlists.length, playlist, false);
      }
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(concurrency, playlists.length) }, () => worker()),
  );
  return { tracksByPlaylist, editableIds, notFoundIds, failures };
}

/**
 * Combined song view across the selected playlists, computed from already-cached tracks (no
 * network): one row per song (deduped by videoId) with the playlists it appears in.
 */
export function combineFromCache(
  selected: Playlist[],
  tracksByPlaylist: Record<string, Track[]>,
): CombinedSong[] {
  // Membership is deduped by playlist *id*, not title: two playlists that happen to share a title
  // still count as two, and a song listed twice within one playlist doesn't inflate the count. The
  // displayed `playlists` array holds titles (resolved per id).
  const byVideo = new Map<string, CombinedSong & { _ids: Set<string> }>();
  for (const playlist of selected) {
    for (const track of tracksByPlaylist[playlist.id] ?? []) {
      const existing = byVideo.get(track.videoId);
      if (existing) {
        if (!existing._ids.has(playlist.id)) {
          existing._ids.add(playlist.id);
          existing.playlists.push(playlist.title);
        }
      } else {
        byVideo.set(track.videoId, { ...track, playlists: [playlist.title], _ids: new Set([playlist.id]) });
      }
    }
  }
  return [...byVideo.values()].map(({ _ids, ...song }) => song);
}

// Conservative Spotify->YouTube matcher (ported from the Python app's spotify_matcher).
function normalizeSearchText(text: string): string {
  return (text || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}_\s]/gu, "")
    .replace(/\s+/g, " ")
    .trim();
}
function tokenSet(text: string): Set<string> {
  return new Set(normalizeSearchText(text).split(" ").filter(Boolean));
}
function isConfidentMatch(tTitle: string, tArtist: string, cTitle: string, cArtist: string): boolean {
  const tT = tokenSet(tTitle);
  const cT = tokenSet(cTitle);
  if (!tT.size || !cT.size) return false;
  const subset = (a: Set<string>, b: Set<string>) => [...a].every((x) => b.has(x));
  if (!(subset(tT, cT) || subset(cT, tT))) return false; // one title's words ⊆ the other's
  const tA = tokenSet(tArtist);
  if (!tA.size) return true; // no source artist → title match is enough
  const cA = tokenSet(cArtist);
  return [...tA].some((x) => cA.has(x)); // ≥1 artist word overlaps
}

/** First confident match among relevance-ranked candidates, or null. */
export function bestYoutubeMatch(
  candidates: MatchCandidate[],
  title: string,
  artist: string,
): MatchCandidate | null {
  for (const c of candidates) {
    if (isConfidentMatch(title, artist, c.title, c.artist)) return c;
  }
  return null;
}
