# Project Status

Living board of what's planned, in progress, and shipped. Update this file as part of any
feature or bug change. See `CONTRIBUTING.md` for the debug-first → release workflow.

_Last updated: 2026-06-15_

## In progress — debug-gated (`PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS`)

- **YouTube Music queue creation (browser-auth).** Create and open a private temporary
  playlist from selected YouTube playlists, as a workaround for the lack of an official
  streaming API. The write backend was switched from OAuth (which returns HTTP 400 on YT
  Music's internal write endpoints) to ytmusicapi **browser-header auth**. Writes have been
  verified working manually. Entry points: "Play in YouTube Music" + "Queue Headers" sidebar
  buttons, and the Set/Test Queue Headers screen.
  - **Next:** confirm the header-setup UX is smooth, then migrate to release (remove the gate).

## Released — always on (normal and debug builds)

- **Temporary-playlist lifecycle management:**
  - Exit prompt to delete leftover temp playlists, with an "always delete on exit" preference
    (persisted in `app_settings.json`).
  - Startup reminder / auto-cleanup of leftovers.
  - Settings → "Temporary Playlists": count, auto-delete checkbox, and "View Temporary
    Playlists" list (title, created timestamp, relative age, merged-from sources) with per-row
    Open/Delete and Delete All.
- **Single-instance lock** (`app_lock.py`) — prevents two instances racing on the temp-playlist
  records.
- **Atomic + cross-process-locked record writes** (`youtube_music_account.py`).
- **GitHub Pages download page** + in-app release update checker.

## Backlog — to do

- [ ] Migrate the YouTube Music queue feature out of debug into release once trusted.
- [ ] Include Spotify playlists in the queue flow (currently skipped with a notice).
- [ ] Guided in-app browser-header extraction to reduce manual copy/paste friction.

## Known bugs / limitations

- YouTube Music has **no official streaming API**: the embedded player cannot reliably play
  YTM tracks, so the queue workaround opens a temporary playlist on music.youtube.com instead.
- OAuth tokens are **rejected by YT Music's internal write endpoints** (HTTP 400 "invalid
  argument") — this is why queue writes use browser-header auth rather than OAuth/Data API.
- **Browser headers expire** when the Google session changes; the user must re-copy them. The
  app detects auth-like failures and prompts to refresh.
