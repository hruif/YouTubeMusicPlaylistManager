# Tauri Rewrite — Investigation & Plan

_Status: proposed (planning only — no code written yet)._
_Last updated: 2026-06-17._

A scoping document for rebuilding YouTube Music Playlist Manager as a
**Tauri (Rust + web frontend)** desktop app, modelled on
[`JustAnotherMusicClient`](https://github.com/) (studied locally from a downloaded copy).
The two motivations: a **native-feeling macOS UI** and an **auth model that doesn't need
constant manual header re-copying**.

This does **not** replace the Python app. The Python app keeps shipping until the rewrite
reaches feature parity (see "Migration strategy").

## Why a rewrite (and not an incremental fix)

Two things we want can't both be had in the current Python/Tkinter stack:

1. **No-reauth auth.** Today the user manually copies a *frozen* header snapshot from an
   external browser; Google rotates the session cookies (~hourly) and the snapshot dies.
   JustAnotherMusicClient instead embeds its **own** persistent login session and reads
   fresh, auto-rotated cookies from it — no manual copying, ever.
2. **Native UI.** Their "native macOS feel" is hand-built React/CSS inside a system WebView.
   Tkinter (aqua theme) fundamentally cannot reproduce it; at best we *approximate*. A true
   match requires a web frontend, i.e. a different stack.

A Tauri rewrite gets both at once.

## What JustAnotherMusicClient actually does (confirmed from its source)

- **Stack:** Tauri 2 + React + TypeScript (frontend) + Rust (backend). Apache-2.0 licensed.
- **Auth (`src-tauri/src/lib.rs::sign_in_youtube_music`):** opens a native `WebviewWindow`
  (WKWebView on macOS) with a **Safari user-agent**, navigated to the YouTube Music Google
  sign-in. The user logs in normally. It **polls the webview's cookie store**
  (`window.cookies()`) until the auth cookies (`SAPISID` / `__Secure-1PAPISID` /
  `__Secure-3PAPISID`) appear on `music.youtube.com`, captures the full cookie jar, and stores
  it **encrypted** (AES key in the OS keyring + a `…-session-v1.bin` file, chunked keyring
  fallback).
- **API:** all calls (read + write) go through a Rust HTTP proxy (`proxy_http_request`,
  `reqwest`) carrying those cookies; request building is done by **`youtubei.js` (InnerTube)**.
- **Key insight that unblocks us:** our STATUS "Known limitations" note says page JS can't read
  the `httpOnly` auth cookies (true — that killed the bookmarklet / Option-B ideas). But the
  **native WebView cookie store is not page JS** — the app owns the webview, so it can read
  `httpOnly` cookies. That's exactly how Tauri does it, and it's why this approach works where
  the rejected ones didn't. **It is not Option B** (no reading of an *external* browser's
  Keychain-encrypted store), so it doesn't carry Option B's trust problem.

## Licensing

JustAnotherMusicClient is **Apache-2.0**, so we may **adapt its code directly** (notably the
auth + cookie storage — the hard, novel part) provided we:

- keep their copyright/license notices on adapted files, and
- ship a `NOTICE` file attributing the project.

This is a major de-risk: the hardest component is borrowable rather than rediscovered.

## Feature parity target

The rewrite must reproduce what the Python app already does (see `README.md` /
`dev-docs/STATUS.md` — those are the spec). Grouped by porting difficulty:

### Ports cleanly (low risk)
- **WebView sign-in + cookie storage** — adapt their Rust almost verbatim.
- **YT read** (library, playlist tracks) and **add song** — `youtubei.js`, proven in their code
  (`client.playlist.addVideos`).
- **Pure logic / heuristics** — conservative Spotify→YT matching, dedup-by-`videoId`, in-playlist
  repeat detection, unavailable-track categorisation (`queueStatus`), custom-name keying,
  removed-songs diff, CSV export. These are documented algorithms with existing Python test
  coverage; re-express in TypeScript and port the tests.

### New / unproven work (real risk — validate early)
- **YT write ops we use but they don't.** They only call `addVideos` / `addToLibrary` /
  `removeFromLibrary`. We also need **create playlist, remove-by-`setVideoId`, delete playlist,
  remove-repeats**. `youtubei.js` exposes these (`playlist.create` / `removeVideos` /
  `delete` / `moveVideo`), but those paths are *unexercised in their codebase* → validate them,
  especially `setVideoId`-based removal and ownership detection (`setVideoId` is only returned
  for playlists you own — the same gotcha that bit the Python app).
- **Spotify import + transfer (biggest gap).** JustAnotherMusicClient has **zero** Spotify
  support; the Python app reads public Spotify playlists via `spotapi` and does Spotify→YouTube
  transfer. No clean JS equivalent of `spotapi` exists. Options: Spotify Web API
  (client-credentials flow reads public playlists with no user login) or a scraper — a genuine
  reimplementation, not a port. Review terms either way.
- **Entire UI** rebuilt in React: sidebar, the sortable/duplicate-merging combined song table,
  Details windows, Settings, every dialog. This is the bulk of the effort and the only way to
  get the native-feeling UI.
- **Local features** that touch the OS: temp-playlist lifecycle + exit prompt, single-instance
  lock, data-dir layout (`saved_playlists.json`, `custom_song_names.json`, `removed_songs.json`,
  `unmatched_songs.json`, settings), update checker.

### Upside
- Tauri's **signing/notarization** pipeline is better than the current PyInstaller + `ditto`
  workaround (which only ad-hoc signs → the "damaged" Gatekeeper friction).

## Effort

**Large — realistically weeks.** It's a rewrite of everything except the auth (borrowed) and the
algorithms (translated). Mitigating factor: the scope is **fully specified** — README + STATUS +
the test suite define "done", so there's no requirements ambiguity.

## Phased plan (de-risk before committing to the UI)

- **Phase 0 — Spike (smallest, highest-value).** Scaffold a minimal Tauri app in this repo, port
  the WKWebView login + cookie capture, and prove the whole premise: sign in once, then do **one
  real read + one real write (add a song)** on the owner's account **with no manual headers**.
  Also smoke-test a `youtubei.js` **create** and **remove-by-`setVideoId`** to retire the biggest
  unknown. If this works, the bet is validated cheaply; if `youtubei.js` writes or cookie refresh
  disappoint, little is lost.
- **Phase 1 — Read-only parity.** Library list + combined song view (sort, duplicate-merge,
  source logos, Search box).
- **Phase 2 — Edits + ownership.** Add / remove / create / remove-repeats; ownership detection;
  optimistic UI with revert; bulk edits.
- **Phase 3 — Spotify.** Public-playlist import + conservative transfer + persisted unmatched list.
- **Phase 4 — Polish & local features.** Custom names, removed-songs archive, export, unavailable
  finder, temp-playlist flow, single-instance lock, update checker, packaging + notarization.

## Migration strategy

- **Location:** a subfolder in this repo (e.g. `tauri/` or `desktop/`) so both apps live together
  during the transition and share issues/docs.
- **Keep the Python app alive and shipping** until the rewrite hits parity — do not delete working
  features mid-flight. Cut over only when Phases 1–4 are done and manually verified.
- **Data:** decide whether to migrate existing `data/*.json` or re-import playlists on first run
  (re-import is simpler; the playlists are cheap to re-add).

## Open decisions (settle before scaffolding begins)

- Tauri 1 vs **Tauri 2** (2 is current; their app uses 2 — match it).
- Spotify source: client-credentials Web API vs scraper.
- Cookie-refresh cadence: keep a hidden webview alive vs re-open on demand to re-read rotated
  cookies (their model implies a persistent app-owned session).
- Cross-platform scope: the Python app is macOS-first; decide whether the rewrite stays macOS-only
  (simpler signing, WKWebView cookie story) or targets Windows/Linux too.
