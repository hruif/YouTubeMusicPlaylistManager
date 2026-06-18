# Project Status

Living board of what's planned, in progress, and shipped. Update this file as part of any
feature or bug change. See `CONTRIBUTING.md` for the debug-first → release workflow.

_Last updated: 2026-06-17_

## In progress — debug-gated (`PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS`)

- _Nothing is currently gated._ The flag and `_show_youtube_queue_actions()` remain as the
  reusable gating mechanism for the next experimental feature (see `CONTRIBUTING.md`).

## Released — always on (normal and debug builds)

This section lists actual app functionality. Internal refactors, build/infra plumbing, and
cosmetic UI tweaks are intentionally not tracked here — see `git log` and `CONTRIBUTING.md`
for architecture/layout.

- **Add / remove songs on your real YouTube Music playlists.** Account-touching writes via the
  same browser-auth client as the queue feature (YouTube only).
  - **Surfaces:** a right-click context menu on the song lists — "View Songs" and the duplicates
    list — ("Add to playlist ▸" / "Remove from playlist ▸" submenus, plus Details/Play), and an
    "Edit on YouTube Music" section in the song Details window (per-playlist Remove buttons + an
    "Add to playlist" dropdown). The Details section shows wherever song details open.
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
  - **Bulk edits.** Multi-select songs (shift/⌘-click) in the song lists → right-click →
    "Add N songs to playlist" / "Remove N songs from playlist" (the remove submenu lists the
    playlists the selection actually appears in). Batched into a single `add_songs` /
    `remove_songs` request, optimistic with revert; add skips songs already present, remove
    confirms first. Non-YouTube songs in the selection are skipped (noted in the menu).
  - **Live count refresh.** After any edit, just the affected playlist's sidebar "(N songs)"
    label is updated in place (`_update_playlist_count_labels`) — no list rebuild, so no flicker
    or scroll reset; the Saved Playlists list / Details refresh too.
- **Session health + playlist ownership awareness.**
  - **Pre-flight session check (before the work).** Header-requiring *long* operations — "Play in
    YouTube Music" (queue) and "Create Playlist" — verify the saved session is still signed in
    (`_verify_session_then` → `session_is_authenticated`, on a worker thread) **before** starting,
    so they don't grind for seconds and then fail at the end on expired headers; if expired, they
    prompt to refresh up front. (No startup popup — the check happens at the point of action.)
  - **Ownership marking (launch).** Shortly after launch (when queue headers exist), a background
    check (`_check_queue_session_health`) learns which saved playlists you own via a single
    `get_library_playlists` call, matched by normalized id (`_normalize_playlist_id` strips the
    `VL` prefix). It's ownership-only and non-intrusive (no popup, doesn't flip the queue's auth
    state). YouTube only lets you edit playlists you own, so edit surfaces that
    require ownership now respect it — "Add to playlist" targets (single + bulk) drop playlists you
    don't own, "Remove repeated songs" is disabled for them, and a playlist's Details shows an
    "Owned by you" row. `_is_playlist_editable` blocks only on a *known* `owned == False` (unknown
    ownership stays editable). Ownership is only marked from a real, non-empty library fetch, so a
    failed/empty/stale fetch can't wrongly flag your own playlists. Covered by
    `tests/test_ui_helpers.py`.
- **Create a real playlist.** Make a new **permanent** YouTube Music playlist (PRIVATE) from a
  selection of **songs** (right-click → "New playlist from … song(s)…") or from the combined songs
  of **selected playlists** (sidebar "Create Playlist from Selected"). Prompts for a name, creates
  it via the shared `QueueService.create_playlist_with_videos` (seed + adaptive-chunk add,
  extracted from the temp-queue path), then **imports it into your saved playlists** so it shows up
  immediately. Reports how many songs were added (and any that couldn't be). Covered by
  `tests/test_queue_service.py`.
- **Remove repeated songs (within one playlist).** Per-playlist action (Saved Playlists
  right-click + that playlist's Details, YouTube only) that deletes the *extra* copies of any
  song listed more than once **in that single playlist**, keeping the first. Confirms first,
  fetches the playlist for `setVideoId`s (`playlist_editor.find_repeat_items` keeps the first
  occurrence of each `videoId` and returns the rest), removes them via `remove_repeats`, then
  de-dupes the local cache (`dedupe_local_tracks`). Reports the count removed (or "none found").
  **Terminology:** these in-playlist copies are **"repeats"** — distinct from the existing
  cross-selection **"Duplicates"** finder ("Find Duplicates in Selection"), which lists songs that
  appear across your *selected* playlists. Covered by `tests/test_playlist_editor.py`.
  - **Editable-playlist + stale-session detection.** Edits only work on playlists you own
    (YouTube only returns `setVideoId` for those). `_require_editable` distinguishes the two
    `owned=False` causes via `session_is_authenticated` (a `get_account_info` check): a
    **stale/expired session** (reads public data but isn't signed in — empty library, no account
    info) raises a "no longer signed in" error that routes to `_prompt_browser_auth_refresh`,
    while a genuinely-someone-else's playlist says so. Also fixed **Test Saved Headers**, which
    used `get_library_playlists` (returns `[]` silently on a stale session → false "worked") to
    additionally require a signed-in account.
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
  The list also has a **right-click menu** (Playlist details / Open in browser / Delete).
- **Preserve & export removed songs.** Your local cache is a snapshot until you Update; Update
  then replaces it with the fresh fetch and would silently drop any song YouTube/Spotify removed.
  Now, **on Update**, the app diffs old vs new tracks and archives the **title + artist** (no link
  — it's dead) of anything that vanished into a per-playlist **"Removed Songs"** list, shown in
  that playlist's Details window (with relative date). The update-complete summary reports how many
  were saved. A guard skips archiving when the fresh fetch is empty (so a failed fetch can't wipe a
  playlist into the archive). Captures removals **from the next update onward** (no record exists
  for songs lost before this shipped). Also a **manual "Export…"** action (playlist Details +
  right-click) writes the current tracks (title/artist/source/id) to a **CSV** you choose.
  Mechanics: `services/removed_songs.py` (`diff_removed_tracks` + `RemovedSongsStore` →
  `removed_songs.json`) and `services/playlist_export.py` (`build_csv`); covered by
  `tests/test_removed_songs.py` + `tests/test_playlist_export.py`.
- **Spotify → YouTube transfer.** Right-click a saved **Spotify** playlist (or use its Details) →
  **"Convert to YouTube playlist…"** to recreate it on YouTube Music: each Spotify track is matched
  by a YouTube Music songs-search, a new playlist is created from the **confident** matches
  (`create_playlist_with_videos`) and imported. Anything not confidently matched is **persisted**
  (`services/unmatched_songs.py` → `unmatched_songs.json`, keyed by the new playlist) and shown in
  that playlist's Details under **"Unmatched from Spotify"**, each row with a **"Search on YouTube
  Music"** link — so the list survives restarts and you can find and add each song by hand.
  **Conservative matching** (`services/spotify_matcher.py`): a candidate
  must have a title-token subset match *and* an artist-word overlap, so it avoids wrong
  versions/covers at the cost of more manual follow-up. Runs one search per track on a worker
  thread behind a progress window; reuses `_verify_session_then` for the up-front session check.
  Matcher logic covered by `tests/test_spotify_matcher.py`.
  - ⚠ **Verification note:** the matcher is unit-tested and the create/import path is the same one
    the create-playlist feature uses, but the end-to-end transfer (live search quality, large
    playlists/rate limits) hasn't been manually run yet — see `MANUAL_TESTING.md` §F.
- **Find unavailable songs.** Sidebar **"Find Unavailable in Selection"** lists songs still in
  the selected playlists that can't actually be played — deleted / region-locked / missing a video
  — by their computed `queueStatus` (`BROKEN_QUEUE_STATUSES = {"Unavailable", "No video ID"}`,
  `_find_unavailable_entries`). It's a full song table with the same right-click **add/remove**
  menu, so the report doubles as a cleanup tool (find dead songs → remove them in bulk).
  Complements the removed-songs archive (which covers songs *dropped* from a playlist).
  Implemented on a shared `views/song_results_view.py` (generalized from the old duplicates view;
  the duplicates finder now uses it too). Covered by `tests/test_ui_helpers.py`.
  - ⚠ **Verification note:** the finder *logic* is unit-tested (`_find_unavailable_entries`, plus a
    `_find_duplicate_entries` regression test), and the table is the same code the duplicates
    finder already used — but the end-to-end UI for this feature hasn't been manually run yet
    (no test data with unavailable tracks was on hand). Run the "Find Unavailable in Selection"
    check in `MANUAL_TESTING.md` §A before the next release.
- **Custom song names (local aliases).** Set a custom name on a song — right-click it ("Set
  custom name…") or use the editable field in its Details window — to make hard-to-type/foreign
  titles easy to find. Local-only metadata (`services/custom_names.py` →
  `custom_song_names.json`), keyed by the normalized title+artist so the alias follows the song
  across playlists. Aliases are always **searchable** in the in-list Search box and shown in a
  **Custom Name** column on the song lists (View Songs + duplicates); the real title always stays
  in Details. A Settings toggle, **"Replace song titles with custom names in lists"**
  (`REPLACE_TITLES_WITH_CUSTOM_NAMES`), instead shows the alias in place of the title and hides the
  column (live via `displaycolumns`). Covered by `tests/test_custom_names.py`.
- **In-list Search box.** Each display (View Songs, duplicates, saved playlists) has a Search box
  that filters its rows instantly as you type (`_create_display_find_controls` +
  `text_utils.matches_find_query`); Ctrl/Cmd+F focuses it (`_focus_active_find`). This is the only
  search path — select all sidebar playlists to search the whole library in View Songs. (Replaced
  the old global Search screen; see Removed.)
- **In-app release update checker.** Checks for newer published releases and notifies the user
  when one is available.
- **Single-instance lock** (`app_lock.py`) — prevents two instances racing on the temp-playlist
  records. The lock lives in the same data dir as those records (`private_user_data_path`), so
  every instance that shares the records shares the lock — from-source runs, separate repo
  checkouts, and the release bundle all coordinate; the debug bundle (separate data dir) gets its
  own lock. It is no longer written into the repo when running from source.

## Backlog — to do

- [ ] **UI revamp / successor app — Tauri rewrite (major, in progress).** Rebuild as a **Tauri**
  (Rust + web frontend) desktop app to fix the manual-header auth friction and get a modern UI.
  Decision recorded in `dev-docs/FUTURE_DIRECTIONS.md` (Tauri chosen over Qt/Electron on a
  best-product lens — chiefly macOS WKWebView being the most robust path through Google's
  embedded-webview sign-in block, plus footprint and frontend ecosystem). Auth/`youtubei.js`
  approach adaptable under JustAnotherMusicClient's Apache-2.0 license, in a `desktop/` subfolder.
  - **Phase 0 — DONE (validated 2026-06-17).** Embedded WKWebView login works (Google doesn't
    block it), the session persists across launches (silent re-capture — true no-reauth), and
    authenticated read **and** write both work via `youtubei.js` 17.0.1. Auth gotchas (Cookie
    stripped by WKWebView; `Origin` must be set or the SAPISIDHASH is ignored → `yt_li=0`;
    `SAPISID`/`__Secure-3PAPISID` aliasing) documented in `dev-docs/FUTURE_DIRECTIONS.md`. (Final
    manual confirm that a write lands on music.youtube.com still pending.)
  - **Phase 1 — DONE.** YT Music library API (names, full list, private playlists); cache-driven
    (library cached as JSON in the app data dir — instant browsing, network only on explicit
    "Update", concurrent + resilient fetch, pooled HTTP client); virtualized combined sortable song
    view with thumbnails + per-song details; song search (⌘F) + ">1 playlist" filter; multi-select;
    hide playlists ("Manage playlists" + hover-×); staleness indicators + "Update stale"; persisted
    selection/sort; custom right-click menus; light/dark design pass. Deferred: background auto-update.
  - **Phase 2 — DONE.** Edits via right-click + confirmations, optimistic with revert: add/remove
    songs (target pickers), create-from-selection, remove-repeats, delete playlist (hardened:
    type-to-confirm + local archive + "Recently deleted" recreate). Ownership is best-effort (YouTube
    no longer exposes it reliably), so edits attempt + report rejection. 404-prune of
    externally-deleted playlists on update. Error popups for all failures.
  - **Phase 3 — DONE.** Spotify import + transfer, no user setup: full spotapi port in TS
    (`src/lib/spotify.ts` — TOTP token via community secret list, web-player bundle hash, client
    token, paginated GraphQL pathfinder; all via the Rust proxy). Conservative matcher
    (`searchYouTubeMusicSongs` + `bestYoutubeMatch`, ported from `spotify_matcher`); transfer creates
    a playlist from confident matches and persists the unmatched (`cache.unmatched`, viewable via
    right-click). Treated as fragile/non-fatal with clear errors.
  - **Phase 4 — DONE (local features + packaging).** Custom song names (local searchable aliases);
    CSV export (native save dialog); removed-songs archive on update; best-effort unavailable filter
    (placeholder-title detection — youtubei.js exposes no playability flag). Production build works:
    `npm run tauri build` → ~12 MB `.app`/`.dmg` (vs ~148 MB Python), ad-hoc signed (notarization
    needs a paid Apple Developer ID, as with the Python app; `desktop/BUILD.md`). Deferred: in-app
    update checker (until the app has its own release line); icon still the Tauri default.
  - **Remaining before cutover:** real app icon, manual end-to-end pass, decide release/versioning
    + whether to notarize, then point the download page at the Tauri build.
  - Remaining risks: the embedded-login + spotapi paths depend on continuing to evade Google's /
    Spotify's changes (fragile by nature; Chrome extension is the immune fallback for YouTube auth).
  The Python app keeps shipping until parity.
- [ ] Include Spotify playlists in the queue flow (currently skipped with a notice). Could now
  reuse `services/spotify_matcher.py` to match Spotify tracks to YouTube videos before queueing.
- ~~Guided in-app browser-header extraction to reduce manual copy/paste friction.~~ **Not
  pursuing.** The only approach that actually removes the painful step (the DevTools dance)
  was reading the browser cookie store directly, and that was rejected on trust grounds (see
  Known bugs / limitations). The remaining "guided clipboard paste" ideas (auto-detect the
  paste, validate, auto-test) only smooth the final paste — they don't touch the real friction
  — and the existing on-screen step-by-step guide + the lenient header parser already cover that
  well. The manual flow is the accepted answer. (If anything is ever worth adding, it's inline
  validation feedback so a bad/incomplete paste is caught before the user assumes it worked.)

## Removed

- **Global Search screen** (the sidebar "Search songs" box/button, `on_search`,
  `_find_matching_tracks`, `show_search_results_display`, and `views/search_results_view.py`).
  Superseded by the in-list Search box (above): View Songs + its Search box is a strict superset —
  same cached-track data, but a sortable table with source logos, the Playlists column, and
  right-click add/remove, versus the old read-only text list. "Select All" in the sidebar
  reproduces the old all-playlists scope. The "Find" boxes were renamed "Search" to match.
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
