# Project Status

Living board of what's planned, in progress, and shipped. Update this file as part of any
feature or bug change. See `CONTRIBUTING.md` for the debug-first → release workflow.

_Last updated: 2026-06-15_

## In progress — debug-gated (`PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS`)

- _Nothing is currently gated._ The flag and `_show_youtube_queue_actions()` remain as the
  reusable gating mechanism for the next experimental feature (see `CONTRIBUTING.md`).

## Released — always on (normal and debug builds)

- **View Songs is the primary, default view.** Renamed from "View Combined Songs", styled as the
  primary sidebar button, and shown on launch (tracks the sidebar selection live). The Playlists
  column is compact + resizable; full lists appear in a song's Details window.
- **YouTube Music queue creation (browser-auth).** "Play in YouTube Music" creates and opens a
  private temporary playlist from the selected YouTube playlists — a workaround for the lack of
  an official streaming API. The write backend uses ytmusicapi **browser-header auth** (OAuth
  returns HTTP 400 on YT Music's internal write endpoints; browser headers have no quota).
  Header setup is a one-time step in Settings > Set Queue Headers. The video list is
  de-duplicated before adding, and rejected songs (deleted/private/region-locked) are reported.
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

- [ ] Include Spotify playlists in the queue flow (currently skipped with a notice).
- [ ] Guided in-app browser-header extraction to reduce manual copy/paste friction.

## Removed

- **Embedded local queue player** (the old `youtube_player.py` / `youtube_player_window.py` /
  `web/youtube_queue_player.html`, the "Play Queue" / "Play YouTube Queue" actions, the
  "Playback" columns, and the `pywebview` dependency). Deleted because YouTube Music tracks
  cannot reliably stream through the embed; the project relies on ytmusicapi playlist creation
  instead. The lightweight track classification it left behind is kept only to pick a good seed
  song for temporary-playlist creation.

## Known bugs / limitations

- YouTube Music has **no official streaming API**: in-app playback isn't possible, so the queue
  workaround opens a temporary playlist on music.youtube.com instead.
- OAuth tokens are **rejected by YT Music's internal write endpoints** (HTTP 400 "invalid
  argument") — this is why queue writes use browser-header auth rather than OAuth/Data API.
- **Browser headers expire** when the Google session changes; the user must re-copy them. The
  app detects auth-like failures and prompts to refresh.
