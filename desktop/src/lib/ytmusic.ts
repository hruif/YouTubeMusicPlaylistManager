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

/** Write test — add a video to a playlist you own. */
export async function addVideo(playlistId: string, videoId: string): Promise<void> {
  await requireClient().playlist.addVideos(normalizePlaylistId(playlistId), [videoId.trim()]);
}

/** Cleanup for the write test. */
export async function removeVideo(playlistId: string, videoId: string): Promise<void> {
  await requireClient().playlist.removeVideos(normalizePlaylistId(playlistId), [videoId.trim()]);
}
