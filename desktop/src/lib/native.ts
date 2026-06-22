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
  openExternal: (url: string) => Promise<void>;
  onCloseRequested: (cb: () => void) => () => void;
};

const electron = (globalThis as unknown as { electronAPI?: ElectronAPI }).electronAPI;
export const isElectron = Boolean(electron?.isElectron);

export function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  return isElectron
    ? (electron!.invoke(cmd, args) as Promise<T>)
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

export async function openExternal(url: string): Promise<void> {
  if (isElectron) return electron!.openExternal(url);
  await tauriOpenUrl(url);
}
