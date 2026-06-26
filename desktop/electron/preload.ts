// Preload: the only bridge between the sandboxed renderer and the main process. Exposes a small,
// explicit surface on window.electronAPI — a generic invoke (mirroring Tauri), window controls, and
// a close-requested subscription for the exit-cleanup prompt.

import { contextBridge, ipcRenderer } from "electron";

const api = {
  isElectron: true as const,
  invoke: (cmd: string, args?: Record<string, unknown>): Promise<unknown> =>
    ipcRenderer.invoke("invoke", cmd, args ?? {}),
  showWindow: (): Promise<void> => ipcRenderer.invoke("window:show"),
  setBackgroundColor: (color: [number, number, number]): Promise<void> =>
    ipcRenderer.invoke("window:set-background", color),
  allowCloseAndQuit: (): Promise<void> => ipcRenderer.invoke("window:allow-close-and-quit"),
  deferClose: (): Promise<void> => ipcRenderer.invoke("window:defer-close"),
  openExternal: (url: string): Promise<void> => ipcRenderer.invoke("open-external", url),
  onCloseRequested: (cb: () => void): (() => void) => {
    const listener = () => cb();
    ipcRenderer.on("close-requested", listener);
    return () => ipcRenderer.removeListener("close-requested", listener);
  },
  installUpdate: (zipUrl: string): Promise<boolean> => ipcRenderer.invoke("update:install", zipUrl),
  onUpdateProgress: (cb: (pct: number) => void): (() => void) => {
    const listener = (_e: unknown, pct: number) => cb(pct);
    ipcRenderer.on("update:progress", listener);
    return () => ipcRenderer.removeListener("update:progress", listener);
  },
};

contextBridge.exposeInMainWorld("electronAPI", api);

export type ElectronAPI = typeof api;
