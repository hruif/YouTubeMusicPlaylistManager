// Platform abstraction for the renderer. Routes the handful of "native" calls (command invoke,
// window controls, opening external links) to either the Electron preload bridge or the Tauri APIs,
// chosen at runtime. Lets the same React UI run under either shell during the migration.

import { invoke as tauriInvoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { openUrl as tauriOpenUrl } from "@tauri-apps/plugin-opener";

type ElectronAPI = {
  isElectron: true;
  invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
  showWindow: () => Promise<void>;
  setBackgroundColor: (color: [number, number, number]) => Promise<void>;
  allowCloseAndQuit: () => Promise<void>;
  deferClose: () => Promise<void>;
  openExternal: (url: string) => Promise<void>;
  playExternal: (url: string, background: boolean) => Promise<PlayFallback>;
  requestBackgroundPermission: () => Promise<string | null>;
  onCloseRequested: (cb: () => void) => () => void;
  installUpdate: (zipUrl: string) => Promise<boolean>;
  onUpdateProgress: (cb: (pct: number) => void) => () => void;
  onTracksProgress: (cb: (p: TracksProgress) => void) => () => void;
};

export type TracksProgress = { playlistId: string; loaded: number; total?: number };

// Per-page progress while a playlist's songs load (Electron only; a no-op elsewhere).
export function onTracksProgress(cb: (p: TracksProgress) => void): () => void {
  return isElectron ? electron!.onTracksProgress(cb) : () => {};
}

const electron = (globalThis as unknown as { electronAPI?: ElectronAPI }).electronAPI;
export const isElectron = Boolean(electron?.isElectron);

// Electron wraps errors thrown in main as "Error invoking remote method 'invoke': Error: <message>".
// Strip that transport prefix so the UI shows only the message the backend meant to show.
export function cleanIpcError(message: string): string {
  return message.replace(/^Error invoking remote method '[^']*': (?:\w*Error: )?/, "");
}

export function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  return isElectron
    ? (electron!.invoke(cmd, args) as Promise<T>).catch((err: unknown) => {
        throw err instanceof Error ? new Error(cleanIpcError(err.message)) : err;
      })
    : tauriInvoke<T>(cmd, args as Record<string, unknown>);
}

export async function showWindow(): Promise<void> {
  if (isElectron) return electron!.showWindow();
  await getCurrentWindow().show();
}

export async function setBackgroundColor(rgb: [number, number, number]): Promise<void> {
  if (isElectron) return electron!.setBackgroundColor(rgb);
  await getCurrentWebviewWindow()
    .setBackgroundColor(rgb)
    .catch(() => {});
}

// Register a handler for a close attempt. The window is held open until the handler calls
// closeWindow(); the handler decides (run cleanup, show a prompt, or close immediately). Returns an
// unlisten function.
export function onCloseRequested(handler: () => void): () => void {
  if (isElectron) return electron!.onCloseRequested(handler);
  let unlisten: (() => void) | undefined;
  void getCurrentWindow()
    .onCloseRequested((event) => {
      event.preventDefault();
      handler();
    })
    .then((u) => {
      unlisten = u;
    });
  return () => unlisten?.();
}

export async function closeWindow(): Promise<void> {
  if (isElectron) return electron!.allowCloseAndQuit();
  await getCurrentWindow().destroy();
}

// Tell the shell we're showing the exit-cleanup prompt, so its force-quit safety timer waits for the
// user. No-op under Tauri (it has no such timer).
export async function deferClose(): Promise<void> {
  if (isElectron) await electron!.deferClose();
}

export async function openExternal(url: string): Promise<void> {
  if (isElectron) return electron!.openExternal(url);
  await tauriOpenUrl(url);
}

// Why a background play opened the usual way instead. `lasting`: it won't work next time either
// (permission refused, or the browser can't), so stop trying.
export type PlayFallback = { reason: string; lasting: boolean } | null;

// Open a song or queue to play. With `background`, the browser opens it behind this window (macOS,
// supported browsers, with permission); otherwise, or if that isn't possible, the usual way.
// Resolves to why it couldn't be done in the background, or null.
export async function playExternal(url: string, background: boolean): Promise<PlayFallback> {
  if (isElectron) return electron!.playExternal(url, background);
  await tauriOpenUrl(url);
  return null;
}

// Ask for permission to control the default browser (for background play). Resolves to why it
// can't be used, or null when it can.
export async function requestBackgroundPermission(): Promise<string | null> {
  if (isElectron) return electron!.requestBackgroundPermission();
  return "Playing in the background isn't available here.";
}

// In-place update (Electron only): download the new build and swap the bundle, then relaunch.
// Resolves as the app is quitting; rejects (so the UI can fall back to a manual download) on failure.
export async function installUpdate(zipUrl: string): Promise<boolean> {
  if (!isElectron) throw new Error("In-place update is not supported in this build.");
  return electron!.installUpdate(zipUrl);
}

// Subscribe to download/install progress (0–100). No-op (returns a no-op unsubscribe) off Electron.
export function onUpdateProgress(cb: (pct: number) => void): () => void {
  if (!isElectron) return () => {};
  return electron!.onUpdateProgress(cb);
}
