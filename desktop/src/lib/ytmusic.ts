// Thin youtubei.js wrapper for the Phase 0 spike: sign in via the embedded webview (interactively
// or silently on startup), then prove a real authenticated read (account/library) and write.

import { Innertube, YTNodes } from "youtubei.js";
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
    // Generate the session/visitor data locally instead of fetching it, and skip retrieving the
    // YouTube player entirely — that's a large JS download + cipher parse used only for streaming,
    // which this app doesn't do. Both cut network round-trips out of client init (faster startup).
    // All our operations (library, playlists, search, add/remove) are InnerTube API calls that
    // don't need the player.
    generate_session_locally: true,
    retrieve_player: false,
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

// A playlist you own carries a MusicEditablePlaylistDetailHeader. Modern YT Music also returns a
// MusicResponsiveHeader, and youtubei.js resolves `playlist.header` to *that* one first — so the old
// `header.type === "..."` check reports false for owned playlists too. The editable node is still in
// the parsed page though, so look for it there (with the header check kept as a fallback).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isPlaylistEditable(playlist: any): boolean {
  if (playlist?.header?.type === "MusicEditablePlaylistDetailHeader") return true;
  try {
    const found = playlist?.page?.contents_memo?.getType(YTNodes.MusicEditablePlaylistDetailHeader);
    return !!found?.length;
  } catch {
    return false;
  }
}

/**
 * Fetch all tracks of a YT Music playlist (paginated), plus whether it's editable (owned).
 */
export async function getPlaylistTracks(
  playlistId: string,
): Promise<{ tracks: Track[]; editable: boolean; title: string }> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let playlist: any = await requireClient().music.getPlaylist(playlistId);
  const editable = isPlaylistEditable(playlist);
  const h = playlist?.header?.title;
  const title: string = (typeof h === "string" ? h : h?.text) ?? "";
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
  return { tracks: out, editable, title };
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

export type MatchCandidate = { videoId: string; title: string; artist: string };

/** Search YouTube Music for songs matching a query; returns relevance-ranked candidates. */
export async function searchYouTubeMusicSongs(query: string): Promise<MatchCandidate[]> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const res: any = await requireClient().music.search(query, { type: "song" });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const items: any[] = res?.songs?.contents ?? res?.contents?.find?.((c: any) => c?.contents)?.contents ?? [];
  const out: MatchCandidate[] = [];
  for (const item of items) {
    const videoId: string | undefined = item?.id;
    const title = typeof item?.title === "string" ? item.title : item?.title?.text;
    if (!videoId || !title) continue;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const artist =
      (item?.artists ?? []).map((a: any) => a?.name).filter(Boolean).join(", ") ||
      (typeof item?.subtitle === "string" ? item.subtitle : item?.subtitle?.text) ||
      "";
    out.push({ videoId, title, artist });
  }
  return out;
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

/**
 * Delete a playlist you own. youtubei.js's `playlist.delete` builds a NavigationEndpoint it can't
 * resolve a URL for ("Expected an api_url"), so call the InnerTube /playlist/delete endpoint
 * directly. Throws if YouTube reports failure (it doesn't always throw on its own).
 */
export async function deletePlaylist(playlistId: string): Promise<void> {
  // Call as a method on `actions` (not a detached fn) so its `this` binding is kept.
  const actions = requireClient().actions as unknown as {
    execute(endpoint: string, args: Record<string, unknown>): Promise<{ success: boolean; status_code: number }>;
  };
  const res = await actions.execute("/playlist/delete", {
    playlistId: normalizePlaylistId(playlistId),
    parse: false,
  });
  const ok = res?.success !== false && (res?.status_code === undefined || res.status_code < 400);
  if (!ok) {
    throw new Error(`YouTube rejected the delete (success=${res?.success}, status=${res?.status_code})`);
  }
}
