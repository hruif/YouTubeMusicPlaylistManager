// Thin youtubei.js wrapper for the Phase 0 spike: sign in via the embedded webview, then prove a
// real authenticated read (account info) and a real write (add/remove a video on a playlist).

import { Innertube } from "youtubei.js";
import { invoke } from "@tauri-apps/api/core";
import { tauriFetch } from "./tauriFetch";

let client: Innertube | null = null;

/** Open the embedded login, capture the session, and create an authenticated youtubei.js client. */
export async function signIn(): Promise<void> {
  const cookie = await invoke<string>("sign_in_youtube_music");
  client = await Innertube.create({
    cookie,
    fetch: tauriFetch,
    generate_session_locally: true,
  });
}

export async function signOut(): Promise<void> {
  await invoke("sign_out_youtube_music");
  client = null;
}

export async function sessionStatus(): Promise<boolean> {
  return invoke<boolean>("session_status");
}

function requireClient(): Innertube {
  if (!client) throw new Error("Not signed in yet.");
  return client;
}

/** Authenticated read — proves the captured session actually works. */
export async function getAccountInfo(): Promise<string> {
  const info = await requireClient().account.getInfo();
  // Shape varies across versions; pull a human-readable name defensively.
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
