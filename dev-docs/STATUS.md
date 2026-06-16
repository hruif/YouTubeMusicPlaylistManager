# Project Status

Living board of what's planned, in progress, and shipped. Update this file as part of any
feature or bug change. See `CONTRIBUTING.md` for the debug-first → release workflow.

_Last updated: 2026-06-16_

## In progress — debug-gated (`PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS`)

- _Nothing is currently gated._ The flag and `_show_youtube_queue_actions()` remain as the
  reusable gating mechanism for the next experimental feature (see `CONTRIBUTING.md`).

## Released — always on (normal and debug builds)

- **Repo reorganized into packages.** App code moved out of the flat root into `views/`
  (the screen builders + `playlist_url_window` + the shared checkbox selector), `services/`
  (`playlist_store`, `text_utils`, `playlist_library`, `queue_service`, `youtube_music_account`,
  `update_checker`), and `tests/` (all `test_*.py`, with a `pytest.ini` setting `pythonpath=.`
  / `testpaths=tests`). The entry point + path-sensitive core stay at the root (`main.py`,
  `ui.py`, `app_info`, `app_paths`, `app_lock`, `app_platform`, `app_settings`) — notably
  `app_paths` uses `__file__` for the from-source data dir, so moving it would relocate user
  data. Imports are package-qualified (`from views import …`, `from services import …`); the
  PyInstaller build was re-verified.
- **Service objects: `PlaylistLibrary` + `QueueService`.** The controller no longer owns
  playlist state/persistence or the YouTube Music queue orchestration (see entries below).
- **Refactor (step 1 of decomposing `ui.py`): pure logic extracted into testable modules.**
  `text_utils.py` (search-text normalization, find-query matching, relative-age/timestamp
  formatting, ellipsis text-fitting, temp-playlist source name/kind/text helpers) and
  `playlist_store.py` (song/track-key generation, storage-key split/join, playlist-identity
  normalization, YouTube source selection, plus the canonical `SOURCE_LABELS`). The controller
  now calls these; `ui.py` shed ~150 lines and ~14 methods. New `test_text_utils.py` /
  `test_playlist_store.py` cover the moved logic directly. **Deferred:** playlist file I/O +
  `saved_playlists` state and the queue-creation/deletion orchestration stay in the controller —
  they are Tk/threading-coupled and belong with the step-2 view extraction.

- **Debug bundle is fully isolated from the release build.** Previously only the bundle *name*
  differed; both builds resolved to the same user-data folder and `instance.lock` (derived from
  `APP_NAME`), so they couldn't run at the same time and shared playlists/headers/temp-records.
  The debug runtime hook now also sets `PLAYLIST_MANAGER_DEBUG_BUILD`, and `app_paths` gives a
  bundled debug build its own `"… (Debug)"` data dir + lock — so release and debug can run side
  by side (e.g. release for normal use, debug for the cookie-stripping experiment). From-source
  runs are unaffected. **Requires rebuilding the debug bundle** (`python tools/build_macos_app.py
  --debug`); existing `dist/` debug builds still share the release data until rebuilt.
- **One-click recovery when the queue session expires.** Auth-like failures during queue
  creation *and* temp-playlist deletion now route through a shared `_prompt_browser_auth_refresh`
  that explains the session expired (Google rotates it periodically — not a sign-out) and offers
  to jump straight to Set Queue Headers. (Exit-time auto-delete stays silent and leaves failures
  recorded for the next launch.)
- **Temp-playlist delete failures now report the real reason.** The "could not be deleted"
  warning previously swallowed the exception; it now shows the underlying error per playlist,
  prints the full error to the console, and detects expired-header (auth) failures to point the
  user at Settings → Set Queue Headers.
- **Startup temp-playlist prompt appears promptly + scroll-anywhere info windows.** The
  "delete leftover temporary playlists?" prompt now fires ~200 ms after launch (was 3.5 s) and is
  parented to the main window, so the user addresses it before clicking around (it's modal, so it
  blocks the main window) — avoiding a misclick when a long-delayed modal suddenly appears. Its
  default button is "No" so an accidental Enter/misclick won't delete (leftovers stay removable
  via Settings → Temporary Playlists). All
  info/details windows (`_create_info_window`: Song, Playlist, Temporary Playlist) now scroll with
  the mouse wheel anywhere in the window, not just over the scrollbar (wheel bound on the Toplevel,
  which is in every descendant's bindtags).
- **Remove saved playlists.** View Saved Playlists has a **"Delete Selected"** button (multi-select
  aware, with a confirmation that clarifies it only removes the local copy, not the playlist on
  YouTube/Spotify); the same Delete action is in the double-click playlist details window. Deletes
  persist via `save_playlists()` and refresh the sidebar selectors live (`_delete_saved_playlists`).
- **Source logos in the temp-playlist views.** The Temporary Playlists list now shows a per-row
  source logo (its `#0` tree column) and "Merged from" lists just the source playlist names — no
  more repeated "YouTube:" text prefix. The temp-playlist details window shows a small source
  logo beside each "Merged from" entry (via `_add_info_row(label_image=…)`). NOTE: ttk.Treeview
  can only show one image per row (the `#0` column), so multiple inline logos live in the
  Frame-based details window, not in table cells. The Temporary Playlists list also resizes
  sensibly: only "Merged from" stretches (the left columns are fixed-width), and its text is
  truncated with an ellipsis to the live column width (`_fit_text_to_pixels`, re-fit on resize /
  column drag) so the list never spills off-screen and widening the window reveals more.
- **Leaner temp-playlist cleanup prompt + per-playlist details.** The startup "delete leftover
  temporary playlists?" prompt now shows just the count (it no longer enumerates each playlist
  with a repeated "from YouTube: …, YouTube: …" source list). Full per-playlist info moved into
  Settings → Temporary Playlists: **double-clicking a row opens a details window** (title,
  created time, age, playlist ID/link, and the full "Merged from" source list) with an "Open in
  Browser" action plus per-source "Open" links. (Double-click used to open the playlist directly;
  the "Open Selected" button still does that.)
- **Search button sits beside the search field.** The Search button now lives directly to the
  right of the search entry (in a shared row) instead of in the action-button stack, so the
  pairing is obvious. "View Songs" remains the styled primary button at the top of the stack.
- **Info-window action buttons align with their row.** In song/playlist Details windows, the
  per-row action button (e.g. "Open") is pinned to the top of its row (`tk.NE`) so it lines up
  with the label and the first line of the value instead of drifting to center when the value
  wraps to multiple lines.
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
  records. The lock lives in the same data dir as those records (`private_user_data_path`), so
  every instance that shares the records shares the lock — from-source runs, separate repo
  checkouts, and the release bundle all coordinate; the debug bundle (separate data dir) gets its
  own lock. It is no longer written into the repo when running from source.
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
  app detects auth-like failures and prompts to refresh. The expiry is driven by Google rotating
  the per-session `__Secure-1PSIDTS` / `__Secure-3PSIDTS` cookies (~hourly), not by the user
  signing out — the saved snapshot just goes stale.
- **Tried & rejected — stripping rotating session cookies.** We tested removing the rotating
  `__Secure-1PSIDTS` / `__Secure-3PSIDTS` cookies from the saved snapshot so ytmusicapi would
  authenticate from the stable SAPISID alone (it recomputes the SAPISIDHASH per request). It did
  **not** extend header lifetime past the ~hourly rotation, so it is off by default. The code
  stays as a reference, opt-in only via `PLAYLIST_MANAGER_STRIP_ROTATING_COOKIES=1`
  (`build_browser_authenticated_client(strip_rotating_cookies=…)`).
