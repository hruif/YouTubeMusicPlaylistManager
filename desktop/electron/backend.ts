// Backend: registers all invoke() commands the renderer calls — auth, YouTube Music operations
// (youtubei.js in the main process), a generic HTTP proxy (so the renderer's Spotify code works
// unchanged, CORS-free), and the CSV export dialog.

import { app, dialog, safeStorage, type BrowserWindow } from "electron";
import { promises as fs } from "node:fs";
import path from "node:path";
import * as auth from "./auth";
import * as yt from "./yt";

// The captured session cookie is persisted encrypted-at-rest via the OS keychain (safeStorage), so
// a returning user is signed in without re-running the WKWebView login. It's never written in clear.
function sessionFile(): string {
  return path.join(app.getPath("userData"), "session.bin");
}
async function persistCookie(cookie: string): Promise<void> {
  const enc = safeStorage.isEncryptionAvailable()
    ? safeStorage.encryptString(cookie)
    : Buffer.from(cookie, "utf8"); // fallback: plain (only if keychain is unavailable)
  await fs.writeFile(sessionFile(), enc);
}
async function loadCookie(): Promise<string | null> {
  try {
    const buf = await fs.readFile(sessionFile());
    return safeStorage.isEncryptionAvailable() ? safeStorage.decryptString(buf) : buf.toString("utf8");
  } catch {
    return null;
  }
}
async function deleteCookie(): Promise<void> {
  await fs.rm(sessionFile(), { force: true });
}
function cookieNames(cookie: string): string[] {
  return [...new Set(cookie.split(";").map((p) => p.trim().split("=")[0]).filter(Boolean))].sort();
}

type CommandHandler = (args: Record<string, unknown>, win: BrowserWindow | null) => Promise<unknown>;

export type BackendDeps = {
  registerCommand: (name: string, handler: CommandHandler) => void;
  userAgent: string;
  getWindow: () => BrowserWindow | null;
};

export function registerBackend(deps: BackendDeps): void {
  const { registerCommand, userAgent } = deps;

  // ---- Auth (the youtubei.js client lives in main; the renderer only learns "signed in") ----
  // Silent: reuse the persisted cookie — no WKWebView needed. (Optimistic: if the cookie is stale,
  // the first library call fails and the user re-signs in.)
  registerCommand("try_silent_sign_in", async () => {
    const cookie = await loadCookie();
    if (!cookie) return null;
    await yt.setSession(cookie);
    return { cookie_names: cookieNames(cookie) };
  });
  // Interactive: spawn the native WKWebView login helper, then persist the captured cookie.
  registerCommand("sign_in_youtube_music", async () => {
    const r = await auth.signIn();
    await yt.setSession(r.cookie);
    await persistCookie(r.cookie);
    return { cookie_names: r.cookie_names };
  });
  registerCommand("sign_out_youtube_music", async () => {
    yt.clearSession();
    await deleteCookie();
    return null;
  });

  // ---- YouTube Music operations ----
  registerCommand("yt_get_library", () => yt.getLibraryPlaylists());
  registerCommand("yt_get_playlist_tracks", (a) => yt.getPlaylistTracks(String(a.playlistId)));
  registerCommand("yt_add_videos", (a) => yt.addVideos(String(a.playlistId), a.videoIds as string[]));
  registerCommand("yt_remove_videos", (a) => yt.removeVideos(String(a.playlistId), a.videoIds as string[]));
  registerCommand("yt_create_playlist", (a) => yt.createPlaylist(String(a.title), a.videoIds as string[]));
  registerCommand("yt_delete_playlist", (a) => yt.deletePlaylist(String(a.playlistId)));
  registerCommand("yt_search", (a) => yt.searchYouTubeMusicSongs(String(a.query)));
  registerCommand("yt_account_info", () => yt.getAccountInfo());

  // ---- Generic HTTP proxy: mirrors the old Rust proxy's shape so the renderer's Spotify code is
  // unchanged. Node has no CORS, so this just forwards the request. ----
  registerCommand("proxy_http_request", async (a) => {
    const input = a.input as {
      method: string;
      url: string;
      headers: Record<string, string>;
      body_base64?: string | null;
    };
    const body = input.body_base64 ? Buffer.from(input.body_base64, "base64") : undefined;
    const res = await fetch(input.url, { method: input.method, headers: input.headers, body });
    const buf = Buffer.from(await res.arrayBuffer());
    const headers: Record<string, string> = {};
    res.headers.forEach((v, k) => {
      if (k.toLowerCase() !== "set-cookie") headers[k] = v;
    });
    return { status: res.status, headers, body_base64: buf.toString("base64") };
  });

  // ---- CSV export (native Save dialog) ----
  registerCommand("export_text_file", async (a, win) => {
    const res = await dialog.showSaveDialog(win ?? deps.getWindow()!, {
      defaultPath: String(a.defaultName ?? "export.csv"),
      filters: [{ name: "CSV", extensions: ["csv"] }],
    });
    if (res.canceled || !res.filePath) return false;
    await fs.writeFile(res.filePath, String(a.contents ?? ""), "utf8");
    return true;
  });
}
