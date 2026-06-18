// Thin youtubei.js wrapper for the Phase 0 spike: sign in via the embedded webview (interactively
// or silently on startup), then prove a real authenticated read (account/library) and write.

import { Innertube } from "youtubei.js";
import { invoke } from "@tauri-apps/api/core";
import { tauriFetch } from "./tauriFetch";

type SignInResult = { cookie: string; cookie_names: string[] };

let client: Innertube | null = null;

// youtubei.js authenticates by reading the literal `SAPISID` cookie. On the .youtube.com domain
// that value is often only present as `__Secure-3PAPISID` (same value, different name), so we add
// a `SAPISID=` entry when it's missing. Without this, requests go out unauthenticated.
function normalizeCookie(cookie: string): string {
  if (/(?:^|;\s*)SAPISID=/.test(cookie)) return cookie;
  const match = cookie.match(/(?:^|;\s*)__Secure-3PAPISID=([^;]+)/);
  return match ? `${cookie}; SAPISID=${match[1]}` : cookie;
}

async function createClient(cookie: string): Promise<void> {
  client = await Innertube.create({
    cookie: normalizeCookie(cookie),
    fetch: tauriFetch,
    generate_session_locally: true,
  });
}

/** Interactive sign-in (visible login window). Returns the captured cookie names (diagnostic). */
export async function signIn(): Promise<string[]> {
  const result = await invoke<SignInResult>("sign_in_youtube_music");
  await createClient(result.cookie);
  return result.cookie_names;
}

/** Startup auto sign-in from the persisted WebView session. Returns names, or null if signed out. */
export async function trySilentSignIn(): Promise<string[] | null> {
  const result = await invoke<SignInResult | null>("try_silent_sign_in");
  if (!result) return null;
  await createClient(result.cookie);
  return result.cookie_names;
}

export async function signOut(): Promise<void> {
  await invoke("sign_out_youtube_music");
  client = null;
}

function requireClient(): Innertube {
  if (!client) throw new Error("Not signed in yet.");
  return client;
}

/** Authenticated read — proves the captured session actually works. */
export async function getAccountInfo(): Promise<string> {
  const info = await requireClient().account.getInfo();
  const contents = info as unknown as {
    contents?: { contents?: Array<{ account_name?: { text?: string } }> };
  };
  const name = contents?.contents?.contents?.[0]?.account_name?.text;
  return name ?? JSON.stringify(info).slice(0, 400);
}

/**
 * List the account's YouTube Music library playlists — names, the full list, and private ones.
 * Uses the YT Music library API (FEmusic_library_landing) filtered to "Playlists", with pagination
 * (the generic yt.getLibrary() used before returned only a partial, unnamed YouTube library).
 * Parser shapes vary, so extraction is defensive (treated as `any`).
 */
export async function getLibraryPlaylists(): Promise<Array<{ id: string; title: string }>> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let library: any = await requireClient().music.getLibrary();

  const filter: string | undefined = (library.filters as string[] | undefined)?.find((f) =>
    /playlist/i.test(f),
  );
  if (filter) {
    try {
      library = await library.applyFilter(filter);
    } catch {
      /* fall back to the unfiltered landing page */
    }
  }

  const out: Array<{ id: string; title: string }> = [];
  const seen = new Set<string>();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const take = (nodes: any[] | undefined): void => {
    for (const node of nodes ?? []) {
      const t = node?.title;
      const title = typeof t === "string" ? t : t?.text;
      const raw = node?.endpoint?.payload?.browseId ?? node?.id;
      if (!raw) continue;
      const id = String(raw).replace(/^VL/, "");
      if (!id.startsWith("PL")) continue; // user/library playlists
      if (seen.has(id)) continue;
      seen.add(id);
      out.push({ id, title: title ?? "(untitled)" });
    }
  };

  // Initial page: contents is an array of sections (Grid/MusicShelf).
  for (const section of (library.contents as unknown[] | undefined) ?? []) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const s = section as any;
    take(s?.items ?? s?.contents);
  }

  // Pagination: each continuation carries one section in `.contents`.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let cont: any = library;
  let guard = 0;
  while (cont?.has_continuation && guard++ < 25) {
    cont = await cont.getContinuation();
    const c = cont?.contents;
    take(c?.items ?? c?.contents);
  }

  return out;
}

// A music.youtube.com playlist URL has `list=VLPLxxxx` or `list=PLxxxx`; addVideos wants the bare
// playlist id, so strip a leading browse-id "VL".
function normalizePlaylistId(playlistId: string): string {
  const id = playlistId.trim();
  return id.startsWith("VL") ? id.slice(2) : id;
}

export type Playlist = { id: string; title: string };
export type Track = { videoId: string; title: string; artist: string; thumb?: string };
export type CombinedSong = Track & { playlists: string[] };

/**
 * Fetch all tracks of a YT Music playlist (paginated), plus whether it's editable (owned) — YT
 * Music returns an editable header only for playlists you own.
 */
export async function getPlaylistTracks(
  playlistId: string,
): Promise<{ tracks: Track[]; editable: boolean }> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let playlist: any = await requireClient().music.getPlaylist(playlistId);
  const editable = playlist?.header?.type === "MusicEditablePlaylistDetailHeader";
  const out: Track[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const take = (items: any[] | undefined): void => {
    for (const item of items ?? []) {
      const videoId: string | undefined = item?.id;
      const title = typeof item?.title === "string" ? item.title : item?.title?.text;
      if (!videoId || !title) continue; // skips ContinuationItem / non-song nodes
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const artist =
        (item?.artists ?? []).map((a: any) => a?.name).filter(Boolean).join(", ") ||
        (typeof item?.subtitle === "string" ? item.subtitle : item?.subtitle?.text) ||
        "";
      // Smallest thumbnail URL (public CDN image; just the URL string is stored).
      const thumbs = item?.thumbnail?.contents ?? item?.thumbnails ?? [];
      const thumb: string | undefined = thumbs[0]?.url;
      out.push({ videoId, title, artist, thumb });
    }
  };
  take(playlist.items);
  let guard = 0;
  while (playlist?.has_continuation && guard++ < 50) {
    playlist = await playlist.getContinuation();
    take(playlist.items);
  }
  return { tracks: out, editable };
}

/**
 * Fetch tracks for many playlists with bounded concurrency, tolerating per-playlist failures
 * (returned in `failures`) so one transient error doesn't abort the whole update.
 */
export async function fetchTracksForPlaylists(
  playlists: Playlist[],
  concurrency = 4,
  onDone?: (done: number, total: number, playlist: Playlist, ok: boolean) => void,
): Promise<{ tracksByPlaylist: Record<string, Track[]>; editableIds: string[]; failures: Playlist[] }> {
  const tracksByPlaylist: Record<string, Track[]> = {};
  const editableIds: string[] = [];
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
      } catch {
        failures.push(playlist);
        onDone?.(++done, playlists.length, playlist, false);
      }
    }
  };
  await Promise.all(
    Array.from({ length: Math.min(concurrency, playlists.length) }, () => worker()),
  );
  return { tracksByPlaylist, editableIds, failures };
}

/**
 * Combined song view across the selected playlists, computed from already-cached tracks (no
 * network): one row per song (deduped by videoId) with the playlists it appears in.
 */
export function combineFromCache(
  selected: Playlist[],
  tracksByPlaylist: Record<string, Track[]>,
): CombinedSong[] {
  const byVideo = new Map<string, CombinedSong>();
  for (const playlist of selected) {
    for (const track of tracksByPlaylist[playlist.id] ?? []) {
      const existing = byVideo.get(track.videoId);
      if (existing) {
        if (!existing.playlists.includes(playlist.title)) existing.playlists.push(playlist.title);
      } else {
        byVideo.set(track.videoId, { ...track, playlists: [playlist.title] });
      }
    }
  }
  return [...byVideo.values()];
}

/** Add videos to a playlist you own. */
export async function addVideos(playlistId: string, videoIds: string[]): Promise<void> {
  await requireClient().playlist.addVideos(normalizePlaylistId(playlistId), videoIds);
}

/** Remove videos from a playlist you own. */
export async function removeVideos(playlistId: string, videoIds: string[]): Promise<void> {
  await requireClient().playlist.removeVideos(normalizePlaylistId(playlistId), videoIds);
}

/** Create a new playlist from the given videos; returns the new playlist id (if reported). */
export async function createPlaylist(title: string, videoIds: string[]): Promise<string | undefined> {
  const res = await requireClient().playlist.create(title, videoIds);
  return res.playlist_id;
}

/**
 * Delete a playlist you own. youtubei.js's `playlist.delete` builds a NavigationEndpoint it can't
 * resolve a URL for ("Expected an api_url"), so call the InnerTube /playlist/delete endpoint
 * directly. Throws if YouTube reports failure (it doesn't always throw on its own).
 */
export async function deletePlaylist(playlistId: string): Promise<void> {
  const execute = requireClient().actions.execute as unknown as (
    endpoint: string,
    args: Record<string, unknown>,
  ) => Promise<{ success: boolean; status_code: number }>;
  const res = await execute("/playlist/delete", {
    playlistId: normalizePlaylistId(playlistId),
    parse: false,
  });
  const ok = res?.success !== false && (res?.status_code === undefined || res.status_code < 400);
  if (!ok) {
    throw new Error(`YouTube rejected the delete (success=${res?.success}, status=${res?.status_code})`);
  }
}
