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

/** List the account's library playlists (target candidates for the write test). */
export async function getLibraryPlaylists(): Promise<Array<{ id: string; title: string }>> {
  const library = await requireClient().getLibrary();
  const playlists = (library as unknown as {
    playlists?: Array<{ id?: string; content_id?: string; title?: { text?: string } | string }>;
  }).playlists ?? [];
  return playlists.map((p) => ({
    id: p.id ?? p.content_id ?? "",
    title: typeof p.title === "string" ? p.title : (p.title?.text ?? "(untitled)"),
  }));
}

/** Write test — add a video to a playlist you own. */
export async function addVideo(playlistId: string, videoId: string): Promise<void> {
  await requireClient().playlist.addVideos(playlistId, [videoId]);
}

/** Cleanup for the write test. */
export async function removeVideo(playlistId: string, videoId: string): Promise<void> {
  await requireClient().playlist.removeVideos(playlistId, [videoId]);
}
