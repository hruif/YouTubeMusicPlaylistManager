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
  openExternal: (url: string): Promise<void> => ipcRenderer.invoke("open-external", url),
  onCloseRequested: (cb: () => void): (() => void) => {
    const listener = () => cb();
    ipcRenderer.on("close-requested", listener);
    return () => ipcRenderer.removeListener("close-requested", listener);
  },
};

contextBridge.exposeInMainWorld("electronAPI", api);

export type ElectronAPI = typeof api;
