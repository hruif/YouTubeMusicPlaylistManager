// Electron main process. Owns the window lifecycle and the privileged backend (cache file I/O,
// auth + youtubei.js, Spotify, dialogs) — the role the Tauri Rust side used to play. The renderer
// reaches it through a single generic `invoke(cmd, args)` channel that mirrors Tauri's invoke, plus
// a few window-control channels. Auth/youtubei.js handlers are filled in by ./backend (Phase 2).

import { app, BrowserWindow, ipcMain, Menu, shell, type IpcMainInvokeEvent, type MenuItemConstructorOptions } from "electron";
import path from "node:path";
import { promises as fs } from "node:fs";
import { registerBackend } from "./backend";
import { stageUpdate } from "./updater";
import { migrateLegacyUserData } from "./migrate";
import { openInBackground, requestPermission } from "./backgroundOpen";

// Distinct app name + dock icon so this is easy to tell apart from other Electron apps (esp. in dev,
// where the dock would otherwise show the generic Electron icon).
app.setName("YouTube Music Playlist Manager");

const isDev = !app.isPackaged;

// The app was called "YouTube Music Manager" until 0.3.5; carry its library and settings over on
// the first run under the new name (see ./migrate). The saved sign-in can't come along (it's
// encrypted with a keychain entry named after the old app), so you sign in once.
if (!isDev) {
  try {
    migrateLegacyUserData(app.getPath("appData"), app.getPath("userData"));
  } catch {
    /* best effort: at worst the app starts fresh */
  }
}
const ICON_PATH = path.join(app.getAppPath(), "build", "icon.png");
const DEV_URL = "http://localhost:1420";

let mainWindow: BrowserWindow | null = null;
// Set true once the renderer has confirmed it's OK to close (exit-cleanup done / user chose close).
let allowClose = false;
// Safety net so a hung/unresponsive renderer can never trap the app open: if it doesn't respond to a
// close request in time, force-quit. Cancelled when the renderer legitimately needs time (exit prompt).
let closeTimer: ReturnType<typeof setTimeout> | null = null;
function clearCloseTimer(): void {
  if (closeTimer) {
    clearTimeout(closeTimer);
    closeTimer = null;
  }
}

// Present the login window as desktop Safari. Google trusts Safari on macOS more loosely than it
// scrutinizes Chrome (which it cross-checks against client hints + engine), so a *consistent* Safari
// impersonation — Safari UA AND no Sec-CH-UA client hints (real Safari sends none) — is the most
// reliable way past the "this browser may not be secure" block. It's also exactly what the working
// Tauri/WKWebView build presents.
const LOGIN_USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15";

function cacheFile(): string {
  return path.join(app.getPath("userData"), "library_cache.json");
}

async function readCache(): Promise<string | null> {
  try {
    return await fs.readFile(cacheFile(), "utf8");
  } catch {
    return null;
  }
}

async function writeCache(contents: string): Promise<void> {
  // Atomic write: temp + rename, so a crash mid-write can't corrupt the cache.
  const tmp = cacheFile() + ".tmp";
  await fs.writeFile(tmp, contents, "utf8");
  await fs.rename(tmp, cacheFile());
}

// Generic command dispatch — mirrors Tauri's invoke(cmd, args). Backend handlers (auth, youtubei.js,
// Spotify, export) register here via registerCommand() from ./backend.
type CommandHandler = (args: Record<string, unknown>, win: BrowserWindow | null) => Promise<unknown>;
const commands = new Map<string, CommandHandler>();
export function registerCommand(name: string, handler: CommandHandler): void {
  commands.set(name, handler);
}

// Built-in cache commands (kept here since they're tiny and have no extra deps).
registerCommand("read_cache", () => readCache());
registerCommand("write_cache", (args) => writeCache(String(args.contents ?? "")));

// Application menu. Electron's default menu binds ⌘R to "Reload", which would wipe the app mid-task
// and swallow the renderer's own ⌘R (refresh selected playlists), so reload/devtools are dev-only.
function buildMenu(): void {
  const template: MenuItemConstructorOptions[] = [
    ...(process.platform === "darwin" ? [{ role: "appMenu" as const }] : []),
    { role: "editMenu" },
    ...(isDev
      ? [{ label: "Developer", submenu: [{ role: "reload" as const }, { role: "toggleDevTools" as const }] }]
      : []),
    { role: "windowMenu" },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 740,
    minWidth: 880,
    minHeight: 560,
    show: false,
    backgroundColor: "#1b1718",
    title: "YouTube Music Playlist Manager",
    icon: ICON_PATH,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) void mainWindow.loadURL(DEV_URL);
  else void mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));

  mainWindow.once("ready-to-show", () => mainWindow?.show());

  // Intercept close so the renderer can run its temp-playlist exit cleanup / prompt. The renderer
  // calls allow_close (then close) when it's done; until then we veto and notify it.
  mainWindow.on("close", (e) => {
    if (allowClose || !mainWindow) return;
    e.preventDefault();
    mainWindow.webContents.send("close-requested");
    clearCloseTimer();
    closeTimer = setTimeout(() => {
      allowClose = true;
      app.quit();
    }, 5000);
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ---- IPC wiring ----
ipcMain.handle("invoke", async (_e: IpcMainInvokeEvent, cmd: string, args: Record<string, unknown>) => {
  const handler = commands.get(cmd);
  if (!handler) throw new Error(`Unknown command: ${cmd}`);
  return handler(args ?? {}, mainWindow);
});

ipcMain.handle("window:show", () => mainWindow?.show());
ipcMain.handle("window:set-background", (_e, _color: [number, number, number]) => {
  // Electron sets the window background at creation; nothing to do per-frame. (No-op kept so the
  // renderer's platform layer has a uniform surface across Tauri/Electron.)
});
ipcMain.handle("window:allow-close-and-quit", () => {
  // The renderer finished its exit cleanup and wants to quit. Quit the whole app — not just close
  // the window — so it doesn't linger in the dock (and so Cmd+Q actually quits on macOS). allowClose
  // lets the upcoming window 'close' through without re-vetoing.
  clearCloseTimer();
  allowClose = true;
  app.quit();
});
// The renderer is showing the exit-cleanup prompt and needs the user to decide — cancel the force-
// quit safety timer so we wait for them instead of quitting out from under the prompt.
ipcMain.handle("window:defer-close", () => clearCloseTimer());
// In-place update: download + stage the new build, then swap the bundle and relaunch. Errors
// propagate to the renderer (which keeps the app running and offers the manual download).
ipcMain.handle("update:install", async (_e, zipUrl: string) => {
  const staged = await stageUpdate(String(zipUrl), (pct) =>
    mainWindow?.webContents.send("update:progress", pct),
  );
  // This is a deliberate restart — skip the exit-cleanup prompt and the force-quit safety timer.
  allowClose = true;
  clearCloseTimer();
  staged.swapAndRelaunch();
  // Give the detached helper a beat to start watching our PID before we exit.
  setTimeout(() => app.quit(), 250);
  return true;
});
// Play a link: in the background (the browser opens a tab behind this window, via AppleScript) when
// asked, else the usual way. Falls back to the usual way on any problem and returns why (and whether
// it's lasting, so the app switches back); null when it went as asked.
const isWebUrl = (url: string): boolean => {
  try {
    return ["https:", "http:"].includes(new URL(url).protocol);
  } catch {
    return false;
  }
};
const defaultBrowser = (): string => app.getApplicationNameForProtocol("https://");
type PlayFallback = { reason: string; lasting: boolean } | null;
ipcMain.handle("play-external", async (_e, url: string, background: boolean): Promise<PlayFallback> => {
  if (!isWebUrl(url)) return null;
  if (background && process.platform === "darwin") {
    const result = await openInBackground(defaultBrowser(), url);
    if (result.ok) return null;
    await shell.openExternal(url);
    return { reason: result.reason, lasting: result.lasting };
  }
  await shell.openExternal(url);
  return null;
});
// Ask for permission to control the default browser now (Settings), not on the first play.
ipcMain.handle("background-permission", async (): Promise<string | null> => {
  if (process.platform !== "darwin") return "Playing in the background is only available on macOS.";
  const result = await requestPermission(defaultBrowser());
  return result.ok ? null : result.reason;
});

ipcMain.handle("open-external", (_e, url: string) => {
  // Only ever hand the OS a web URL — never file://, custom schemes, etc.
  try {
    const { protocol } = new URL(url);
    if (protocol === "https:" || protocol === "http:") return shell.openExternal(url);
  } catch {
    /* malformed URL — ignore */
  }
  return Promise.resolve();
});

// Single-instance: a second launch focuses the existing window instead of racing on the cache.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    if (process.platform === "darwin" && app.dock) {
      try {
        app.dock.setIcon(ICON_PATH);
      } catch {
        /* dev icon is best-effort */
      }
    }
    registerBackend({ registerCommand, userAgent: LOGIN_USER_AGENT, getWindow: () => mainWindow });
    buildMenu();
    createWindow();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  // Single-window utility: closing the window quits the app on every platform (matching the Tauri
  // build), rather than the macOS default of staying alive with no window.
  app.on("window-all-closed", () => app.quit());
}
