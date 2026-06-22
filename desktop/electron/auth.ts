// Auth for the Electron main process: an embedded Google login window whose persistent session
// cookies we capture and hand to youtubei.js — ported from src-tauri/src/lib.rs. A persistent
// session partition keeps the login across launches (so silent sign-in works), mirroring the Tauri
// WKWebView's persistent profile.

import { BrowserWindow, session as electronSession } from "electron";

const PARTITION = "persist:ytmusic";
const LOGIN_URL =
  "https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fmusic.youtube.com%2F";
const MUSIC_URL = "https://music.youtube.com/";

export type SignInResult = { cookie: string; cookie_names: string[] };

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

function ytSession() {
  return electronSession.fromPartition(PARTITION);
}

function onMusicPage(win: BrowserWindow): boolean {
  try {
    return new URL(win.webContents.getURL()).host === "music.youtube.com";
  } catch {
    return false;
  }
}

// Build the Cookie header from the session's youtube.com cookies — but only once a live auth cookie
// is present (so we never capture a half-set session during the accounts.google.com redirect).
async function captureSession(): Promise<SignInResult | null> {
  const cookies = await ytSession().cookies.get({});
  const yt = cookies.filter((c) => c.domain?.replace(/^\./, "").endsWith("youtube.com"));
  const names = yt.map((c) => c.name);
  const hasAuth = ["SAPISID", "__Secure-1PAPISID", "__Secure-3PAPISID"].some((n) => names.includes(n));
  if (!hasAuth) return null;
  const cookie = yt.map((c) => `${c.name}=${c.value}`).join("; ");
  return { cookie, cookie_names: [...new Set(names)].sort() };
}

function openLoginWindow(userAgent: string, visible: boolean, url: string): BrowserWindow {
  const existing = BrowserWindow.getAllWindows().find((w) => w.getTitle() === "Sign in to YouTube Music");
  existing?.close();
  const win = new BrowserWindow({
    width: 520,
    height: 760,
    show: visible,
    title: "Sign in to YouTube Music",
    autoHideMenuBar: true,
    webPreferences: { partition: PARTITION, nodeIntegration: false, contextIsolation: true },
  });
  win.webContents.setUserAgent(userAgent);
  void win.loadURL(url, { userAgent });
  return win;
}

// Interactive: show the Google login window and wait (up to ~5 min) for the session to land on
// music.youtube.com with auth cookies.
export async function signIn(userAgent: string): Promise<SignInResult> {
  const win = openLoginWindow(userAgent, true, LOGIN_URL);
  try {
    for (let i = 0; i < 300; i++) {
      if (win.isDestroyed()) throw new Error("Sign-in was cancelled.");
      if (onMusicPage(win)) {
        const cap = await captureSession();
        if (cap) return cap;
      }
      await delay(1000);
    }
    throw new Error("Sign-in timed out.");
  } finally {
    if (!win.isDestroyed()) win.close();
  }
}

// Silent: load music.youtube.com hidden; a persisted session loads it signed-in and we capture the
// cookies. A signed-out user just sits on music.youtube.com with no auth cookie — bail after ~3s.
export async function trySilentSignIn(userAgent: string): Promise<SignInResult | null> {
  const win = openLoginWindow(userAgent, false, MUSIC_URL);
  try {
    let settled = 0;
    for (let i = 0; i < 75; i++) {
      if (win.isDestroyed()) return null;
      if (onMusicPage(win)) {
        const cap = await captureSession();
        if (cap) return cap;
        if (++settled >= 15) return null;
      } else {
        settled = 0;
      }
      await delay(200);
    }
    return null;
  } finally {
    if (!win.isDestroyed()) win.close();
  }
}

export async function signOut(): Promise<void> {
  await ytSession().clearStorageData();
}
