// Auth: interactive sign-in by spawning the native WKWebView login helper (electron/login-helper).
// Electron's own Chromium login window is blocked by Google, but the helper is a real WKWebView
// (= Safari, which Google trusts). It prints the captured session cookie as JSON; we hand it back.
// Persistence (reusing the cookie on later launches) and sign-out are handled in backend.ts.

import { app } from "electron";
import { execFile } from "node:child_process";
import path from "node:path";

export type SignInResult = { cookie: string; cookie_names: string[] };

function helperPath(): string {
  // Packaged: copied into Resources via electron-builder extraResources. Dev: the esbuild/swiftc
  // output dir next to the app root.
  return app.isPackaged
    ? path.join(process.resourcesPath, "login-helper")
    : path.join(app.getAppPath(), "electron-dist", "login-helper");
}

let inFlight: Promise<SignInResult> | null = null;

// Interactive login. Resolves with the captured cookie, or null if the user cancelled / timed out.
// Concurrent calls share one helper process (so a double-click on "Sign in" can't spawn two windows),
// and the helper is killed if the app quits mid-login rather than orphaned for up to 6 minutes.
export async function signIn(): Promise<SignInResult> {
  if (inFlight) return inFlight;
  inFlight = runHelper().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

async function runHelper(): Promise<SignInResult> {
  const result = await new Promise<SignInResult | null>((resolve, reject) => {
    let child: ReturnType<typeof execFile> | undefined;
    const killChild = (): void => {
      try {
        child?.kill();
      } catch {
        /* already gone */
      }
    };
    app.once("before-quit", killChild);
    child = execFile(
      helperPath(),
      [],
      { timeout: 6 * 60_000, maxBuffer: 4 * 1024 * 1024 },
      (err, stdout) => {
        app.removeListener("before-quit", killChild);
        // The helper prints the JSON (or "null") as its last stdout line; AppKit may log noise.
        const line = (stdout || "").trim().split("\n").filter(Boolean).pop() ?? "null";
        if (err && !stdout) return reject(err);
        if (line === "null") return resolve(null);
        try {
          resolve(JSON.parse(line) as SignInResult);
        } catch {
          resolve(null);
        }
      },
    );
  });
  if (!result) throw new Error("Sign-in was cancelled.");
  return result;
}
