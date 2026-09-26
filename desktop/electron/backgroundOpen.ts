// Open a link in the browser without bringing the browser to the front (macOS). Browsers such as
// Chrome come forward on any normal "open URL", even when asked not to, and macOS doesn't let an app
// take focus back afterwards. The reliable way is to ask the browser directly, over AppleScript, to
// add a tab: that doesn't activate it. The first time, macOS asks the user for permission to control
// the browser (Privacy & Security → Automation).

import { execFile } from "node:child_process";

export type BrowserFamily = "chromium" | "safari";

// Browsers whose AppleScript can add a tab. Names are as macOS reports the default browser.
const SUPPORTED: Record<string, BrowserFamily> = {
  "Google Chrome": "chromium",
  "Google Chrome Beta": "chromium",
  "Google Chrome Dev": "chromium",
  "Google Chrome Canary": "chromium",
  Chromium: "chromium",
  "Microsoft Edge": "chromium",
  "Brave Browser": "chromium",
  Vivaldi: "chromium",
  Arc: "chromium",
  Safari: "safari",
  "Safari Technology Preview": "safari",
};

export function browserFamily(appName: string): BrowserFamily | null {
  return SUPPORTED[appName] ?? null;
}

// The AppleScript that adds a tab with the URL (passed as the script's first argument, so it never
// needs quoting). The app name comes only from SUPPORTED, so it's safe to put in the script.
export function openTabScript(appName: string, family: BrowserFamily): string {
  const body =
    family === "safari"
      ? `if (count of windows) is 0 then
      make new document with properties {URL:theURL}
    else
      tell front window to set current tab to (make new tab with properties {URL:theURL})
    end if`
      : `if (count of windows) is 0 then
      make new window
      set URL of active tab of front window to theURL
    else
      tell front window to make new tab with properties {URL:theURL}
    end if`;
  return `on run argv
  set theURL to item 1 of argv
  tell application "${appName}"
    ${body}
  end tell
end run`;
}

// A harmless request that makes macOS ask for permission now (while the user is in Settings) rather
// than on the first play. Only sent when the browser is already running, so it never launches it.
export function permissionCheckScript(appName: string): string {
  return `if application "${appName}" is running then
  tell application "${appName}" to count windows
end if`;
}

// `lasting`: retrying won't help (permission refused, or the browser can't do it), so the app
// should stop trying and switch back to opening normally.
export type OpenResult = { ok: true } | { ok: false; reason: string; lasting: boolean };

const isDenial = (stderr: string): boolean => /-1743|not authori[sz]ed/i.test(stderr);

// osascript's error text → a sentence for the user.
export function explainFailure(appName: string, stderr: string): string {
  if (isDenial(stderr)) {
    return `Permission to control ${appName} wasn't given. You can allow it in System Settings → Privacy & Security → Automation.`;
  }
  if (/-1728|-1708|can.t get|doesn.t understand/i.test(stderr)) {
    return `${appName} didn't accept the request to open a tab in the background.`;
  }
  return `${appName} couldn't open a tab in the background.`;
}

// `openedNormally`: the link was opened the usual way instead (on play), vs. just checking (Settings).
export function unsupportedReason(appName: string, openedNormally: boolean): string {
  const name = appName || "Your default browser";
  return `${name} can't open tabs in the background${openedNormally ? ", so it opened normally" : ""}. Chrome, Edge, Brave, Arc, Vivaldi, and Safari can.`;
}

// Runs the script; resolves to osascript's error output, or null on success.
function runScript(script: string, args: string[]): Promise<string | null> {
  return new Promise((resolve) => {
    execFile("/usr/bin/osascript", ["-e", script, ...args], { timeout: 15_000 }, (err, _stdout, stderr) => {
      resolve(err ? String(stderr || err.message) : null);
    });
  });
}

const failure = (appName: string, stderr: string): OpenResult => ({
  ok: false,
  reason: explainFailure(appName, stderr),
  lasting: isDenial(stderr),
});

// Open `url` in `appName` (the default browser) in the background.
export async function openInBackground(appName: string, url: string): Promise<OpenResult> {
  const family = browserFamily(appName);
  if (!family) return { ok: false, reason: unsupportedReason(appName, true), lasting: true };
  const stderr = await runScript(openTabScript(appName, family), [url]);
  return stderr === null ? { ok: true } : failure(appName, stderr);
}

// Check (and, the first time, ask for) permission to control `appName`.
export async function requestPermission(appName: string): Promise<OpenResult> {
  if (!browserFamily(appName)) return { ok: false, reason: unsupportedReason(appName, false), lasting: true };
  const stderr = await runScript(permissionCheckScript(appName), []);
  return stderr === null ? { ok: true } : failure(appName, stderr);
}
