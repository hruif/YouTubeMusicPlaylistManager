# Project Status

Living board of what's planned, in progress, and shipped. Update this file as part of any
feature or bug change. See `CONTRIBUTING.md` for the debug-first → release workflow.

_Last updated: 2026-06-16_

## In progress — debug-gated (`PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS`)

- _Nothing is currently gated._ The flag and `_show_youtube_queue_actions()` remain as the
  reusable gating mechanism for the next experimental feature (see `CONTRIBUTING.md`).

## Released — always on (normal and debug builds)

This section lists actual app functionality. Internal refactors, build/infra plumbing, and
cosmetic UI tweaks are intentionally not tracked here — see `git log` and `CONTRIBUTING.md`
for architecture/layout.

- **Add / remove songs on your real YouTube Music playlists.** Account-touching writes via the
  same browser-auth client as the queue feature (YouTube only).
  - **Surfaces:** a right-click context menu on the "View Songs" list ("Add to playlist ▸" /
    "Remove from playlist ▸" submenus, plus Details/Play), and an "Edit on YouTube Music" section
    in the song Details window (per-playlist Remove buttons + an "Add to playlist" dropdown). The
    Details section shows wherever song details open (combined / search / duplicates).
  - **Add targets:** only saved YouTube playlists that don't already contain the song
    (`duplicates=False`). **Remove** asks for confirmation (it deletes from the live account, not
    just the local copy) and fetches the playlist first to get the `setVideoId` ytmusicapi needs.
  - **Mechanics:** `services/playlist_editor.py` (`PlaylistEditor.add_song` /`remove_song` + pure
    helpers `addable_target_playlists`, `find_set_video_ids`, `apply_local_add/remove`, covered by
    `tests/test_playlist_editor.py`). Controller methods `add_song_to_playlist` /
    `remove_song_from_playlist` apply the change to the local copy **optimistically** (the
    refreshed song list is the feedback), then confirm on a worker thread via `_run_account_edit`:
    success persists silently (`save_playlists()`), failure reverts the local change and shows the
    error (auth-expiry → `_prompt_browser_auth_refresh`). **No progress/success popups** — only the
    Remove confirmation and error dialogs. An in-flight guard (`_begin_account_edit`) blocks
    duplicate concurrent writes from fast double-clicks.
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
- **Per-playlist temp-playlist details.** In Settings → Temporary Playlists, double-clicking a
  row opens a details window (title, created time, age, playlist ID/link, and the full "Merged
  from" source list) with an "Open in Browser" action plus per-source "Open" links. ("Open
  Selected" opens the playlist directly.)
- **One-click recovery when the queue session expires.** Auth-like failures during queue
  creation *and* temp-playlist deletion route through a shared `_prompt_browser_auth_refresh`
  that explains the session expired (Google rotates it periodically — not a sign-out) and offers
  to jump straight to Set Queue Headers. (Exit-time auto-delete stays silent and leaves failures
  recorded for the next launch.)
- **Temp-playlist delete failures report the real reason.** The "could not be deleted" warning
  shows the underlying error per playlist, prints the full error to the console, and detects
  expired-header (auth) failures to point the user at Settings → Set Queue Headers.
- **Remove saved playlists.** View Saved Playlists has a **"Delete Selected"** button (multi-select
  aware, with a confirmation that clarifies it only removes the local copy, not the playlist on
  YouTube/Spotify); the same Delete action is in the double-click playlist details window. Deletes
  persist via `save_playlists()` and refresh the sidebar selectors live (`_delete_saved_playlists`).
- **In-app release update checker.** Checks for newer published releases and notifies the user
  when one is available.
- **Single-instance lock** (`app_lock.py`) — prevents two instances racing on the temp-playlist
  records. The lock lives in the same data dir as those records (`private_user_data_path`), so
  every instance that shares the records shares the lock — from-source runs, separate repo
  checkouts, and the release bundle all coordinate; the debug bundle (separate data dir) gets its
  own lock. It is no longer written into the repo when running from source.

## Backlog — to do

- [ ] Include Spotify playlists in the queue flow (currently skipped with a notice).
- ~~Guided in-app browser-header extraction to reduce manual copy/paste friction.~~ **Not
  pursuing.** The only approach that actually removes the painful step (the DevTools dance)
  was reading the browser cookie store directly, and that was rejected on trust grounds (see
  Known bugs / limitations). The remaining "guided clipboard paste" ideas (auto-detect the
  paste, validate, auto-test) only smooth the final paste — they don't touch the real friction
  — and the existing on-screen step-by-step guide + the lenient header parser already cover that
  well. The manual flow is the accepted answer. (If anything is ever worth adding, it's inline
  validation feedback so a bad/incomplete paste is caught before the user assumes it worked.)

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
- **Tried & rejected — reading the browser cookie store directly (Option B).** We prototyped a
  one-click "import from a signed-in browser" via `browser_cookie3` (read the browser's
  `youtube.com` cookies, synthesize the `authorization`/`x-goog-authuser` headers ytmusicapi
  needs, save them). It worked technically, but it requires the macOS **Keychain "Chrome Safe
  Storage"** key to decrypt Chrome's cookies — the *same prompt cookie-stealing malware
  triggers* — and gives the app the capability to read the whole cookie store. That's an
  unacceptable trust ask for a distributed app, so it was **removed entirely** (no code kept).
  The replacement direction is the low-trust guided clipboard paste (see Backlog). Note for
  future attempts: a bookmarklet/in-page JS can't help here either — the critical auth cookies
  (`__Secure-3PSID`, etc.) are `httpOnly`, so page JavaScript can't read them.
