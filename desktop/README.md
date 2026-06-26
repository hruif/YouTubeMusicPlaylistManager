# YouTube Music Manager — native desktop app

The native rewrite of [YouTube Music Playlist Manager](../README.md), built with **Electron** +
**React/TypeScript** (Vite). It's the recommended download — current release `desktop-v0.3.2`, a
universal macOS `.dmg`. The original Python app still works but is no longer the primary download.

## What it does
- **Sign in once, in-app** — a native WKWebView login window captures a YouTube session, so there's
  no more copying browser headers. The session is stored encrypted at rest (macOS Keychain via
  Electron `safeStorage`).
- **Library** — your full YouTube Music playlists (including private), cached locally for instant,
  virtualized browsing; combined sortable song view, search, custom names, hide unwanted playlists.
- **Edit your playlists** — add / remove / create / delete / remove-repeats, optimistic with revert
  and a hardened, recoverable delete.
- **Spotify → YouTube** — import a public Spotify playlist (no setup) and transfer it via conservative
  title+artist matching; unmatched songs are saved for manual follow-up.
- **Local extras** — CSV export, removed-songs archive, best-effort unavailable filter.

## Develop / build
See [`BUILD.md`](BUILD.md). TL;DR:
```bash
npm install
npm run electron:dev     # bundles main/preload + Swift helper, starts Vite, launches Electron
npm run electron:build   # production universal .dmg via electron-builder (output in release/)
```

## How it works (high level)
- **`youtubei.js` runs in the Electron main process** (Node — no CORS or forbidden-header limits) and
  is exposed to the renderer through a single generic `invoke(cmd, args)` IPC channel
  (`electron/main.ts` → `electron/backend.ts` → `electron/yt.ts`).
- **Sign-in** spawns a native Swift WKWebView helper (`electron/login-helper/login.swift`, compiled by
  `electron/build.mjs`): Google trusts WKWebView (= Safari) but blocks Electron's embedded Chromium,
  so the helper captures the youtube.com cookies and hands them to `youtubei.js` (`electron/auth.ts`).
- **Spotify** access is an unofficial port of the Python app's `spotapi` (`src/lib/spotify.ts`),
  routed through a host-allowlisted `proxy_http_request` in the main process; it's fragile by nature,
  so failures are surfaced as non-fatal popups.
- The WebView-login-with-cookie-capture approach is adapted from JustAnotherMusicClient (Apache-2.0);
  see [`NOTICE`](NOTICE).

## Status & background
See the repo's [`dev-docs/STATUS.md`](../dev-docs/STATUS.md) and
[`dev-docs/FUTURE_DIRECTIONS.md`](../dev-docs/FUTURE_DIRECTIONS.md) for the rationale and roadmap (the
desktop app was prototyped on Tauri, then moved to Electron for smooth resizing — keeping the native
WKWebView sign-in via the helper sidecar).
