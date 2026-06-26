// In-place updater (macOS, unsigned). The app has no Apple Developer ID, so it can't use Squirrel /
// electron-updater (those require a valid code signature). Instead we do the swap ourselves:
// download the new build's zipped .app, strip its Gatekeeper quarantine, then a detached helper
// waits for this process to exit, replaces the installed bundle, and relaunches it. The user gets a
// "restart to apply" — no drag-to-Applications, no "open anyway" prompt — without any signing.
//
// Limitations (documented, fall back gracefully): only works on the installed .app (not dev or a
// read-only/translocated image); if the install dir isn't user-writable (e.g. needs admin) the swap
// is aborted and the new app is revealed in Finder for a manual move.

import { app } from "electron";
import { promises as fs, createWriteStream, writeFileSync } from "node:fs";
import path from "node:path";
import os from "node:os";
import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";
import { Readable } from "node:stream";

const execFileP = promisify(execFile);

// Only ever download/execute artifacts served from our own GitHub release host.
function isTrustedUrl(u: string): boolean {
  try {
    const url = new URL(u);
    if (url.protocol !== "https:") return false;
    const h = url.hostname.toLowerCase();
    return h === "github.com" || h.endsWith(".github.com") || h.endsWith(".githubusercontent.com");
  } catch {
    return false;
  }
}

// The installed .app bundle: /Applications/<name>.app/Contents/MacOS/<exe> → three levels up.
export function installedAppPath(): string | null {
  if (!app.isPackaged) return null;
  const bundle = path.resolve(app.getPath("exe"), "..", "..", "..");
  return bundle.endsWith(".app") ? bundle : null;
}

export type StagedUpdate = { swapAndRelaunch: () => void };

// Download + extract + de-quarantine the new build, and return a swap() that replaces the running
// bundle and relaunches. Call swap() right before quitting. Throws (with a user-facing message) if
// anything fails, leaving the current app untouched.
export async function stageUpdate(zipUrl: string, onProgress: (pct: number) => void): Promise<StagedUpdate> {
  if (process.platform !== "darwin") throw new Error("In-place update is supported on macOS only.");
  if (!isTrustedUrl(zipUrl)) throw new Error("Refusing to download an update from an untrusted URL.");
  const dest = installedAppPath();
  if (!dest) {
    throw new Error("In-place update only works on the installed app. Download and install it manually instead.");
  }

  const dir = path.join(os.tmpdir(), `ytmpm-update-${process.pid}`);
  await fs.rm(dir, { recursive: true, force: true }).catch(() => {});
  await fs.mkdir(dir, { recursive: true });
  const zipPath = path.join(dir, "update.zip");
  const extractDir = path.join(dir, "extract");

  // Stream the download to disk, reporting progress (the zip is ~180 MB — don't buffer it in memory).
  const res = await fetch(zipUrl);
  if (!res.ok || !res.body) throw new Error(`Download failed (HTTP ${res.status}).`);
  const total = Number(res.headers.get("content-length")) || 0;
  let received = 0;
  const out = createWriteStream(zipPath);
  const reader = Readable.fromWeb(res.body as Parameters<typeof Readable.fromWeb>[0]);
  reader.on("data", (chunk: Buffer) => {
    received += chunk.length;
    if (total) onProgress(Math.min(99, Math.round((received / total) * 100)));
  });
  await new Promise<void>((resolve, reject) => {
    reader.pipe(out);
    out.on("finish", () => resolve());
    out.on("error", reject);
    reader.on("error", reject);
  });

  // Extract with ditto — the correct tool for macOS .app zips (preserves symlinks + permissions;
  // plain unzip can corrupt the bundle).
  await fs.mkdir(extractDir, { recursive: true });
  await execFileP("/usr/bin/ditto", ["-x", "-k", zipPath, extractDir]);

  const entries = await fs.readdir(extractDir);
  const appName = entries.find((e) => e.endsWith(".app"));
  if (!appName) throw new Error("Update archive did not contain an .app bundle.");
  const newApp = path.join(extractDir, appName);

  // Remove the Gatekeeper quarantine so the relaunched copy isn't blocked with "open anyway".
  await execFileP("/usr/bin/xattr", ["-dr", "com.apple.quarantine", newApp]).catch(() => {});

  onProgress(100);

  const swapAndRelaunch = (): void => {
    const q = (s: string) => s.replace(/(["$`\\])/g, "\\$1");
    const script = `#!/bin/bash
APP_PID="${process.pid}"
SRC="${q(newApp)}"
DEST="${q(dest)}"
# Wait (up to ~60s) for the old app to fully exit so we can replace its bundle.
for _ in $(seq 1 600); do kill -0 "$APP_PID" 2>/dev/null || break; sleep 0.1; done
rm -rf "$DEST.bak" 2>/dev/null
if mv "$DEST" "$DEST.bak" && mv "$SRC" "$DEST"; then
  rm -rf "$DEST.bak" 2>/dev/null
  xattr -dr com.apple.quarantine "$DEST" 2>/dev/null
  open "$DEST"
else
  # Couldn't replace in place (e.g. the install dir needs admin) — restore the original and reveal
  # the new app so the user can move it manually.
  [ -d "$DEST.bak" ] && mv "$DEST.bak" "$DEST" 2>/dev/null
  open -R "$SRC"
fi
`;
    const scriptPath = path.join(dir, "swap.sh");
    // Write + spawn synchronously: we're about to quit, and the detached helper must already be
    // running (it watches our PID) before we go.
    writeFileSync(scriptPath, script, { mode: 0o755 });
    const child = spawn("/bin/bash", [scriptPath], { detached: true, stdio: "ignore" });
    child.unref();
  };

  return { swapAndRelaunch };
}
