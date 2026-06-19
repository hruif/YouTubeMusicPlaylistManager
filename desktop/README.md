# YouTube Music Manager — native (Tauri) app

The native rewrite of [YouTube Music Playlist Manager](../README.md), built with **Tauri (Rust)** +
**React/TypeScript**. Shipped as a coexisting **beta** (GitHub pre-release `desktop-v0.1.0`); the
original Python app remains the primary download for now.

## What it does
- **Sign in once, in-app** — an embedded Google login captures a self-refreshing session, so there's
  no more copying browser headers.
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
npm run tauri dev      # needs Rust: source "$HOME/.cargo/env"
npm run tauri build    # production .app/.dmg
```

## How it works (high level)
- Auth + all API traffic route through a small Rust HTTP proxy (`src-tauri/src/lib.rs`) so the
  session cookies are attached; the frontend talks to YouTube via `youtubei.js`.
- The embedded-WebView login + proxy approach is adapted from JustAnotherMusicClient (Apache-2.0);
  see [`NOTICE`](NOTICE).
- Spotify access is an unofficial port of the Python app's `spotapi` (`src/lib/spotify.ts`) and is
  fragile by nature — failures are surfaced as non-fatal popups.

## Status & background
See the repo's [`dev-docs/STATUS.md`](../dev-docs/STATUS.md) (the "Tauri rewrite" entry) and
[`dev-docs/FUTURE_DIRECTIONS.md`](../dev-docs/FUTURE_DIRECTIONS.md) for the rationale and roadmap.
