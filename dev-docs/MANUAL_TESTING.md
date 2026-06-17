# Manual Testing Guide

Checklists for the parts not covered by `pytest`. Run the relevant section before migrating a
feature to release (see `CONTRIBUTING.md`) or cutting a build. The automated suite still runs
first: `pytest -q`.

## How to run

- Normal / release UI from source:
  ```bash
  python3 main.py
  ```
- Debug UI from source (queue actions visible):
  ```bash
  PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python3 main.py
  ```
- Debug app bundle:
  ```bash
  python tools/build_macos_app.py --debug
  # then open "YouTube Music Playlist Manager (Debug).app"
  ```

## A. Core playlist features (release build)

- [ ] The app opens to the "View Songs" view, and "View Songs" is the primary sidebar button.
- [ ] Add a public YouTube playlist by URL; songs load and persist after restart.
- [ ] Add a public Spotify playlist by URL (requires `spotapi`).
- [ ] The in-list Search box (View Songs / duplicates / saved playlists) filters rows as you
      type; Ctrl/⌘+F focuses it. (There is no separate global Search screen.)
- [ ] View Songs: selecting/deselecting playlists updates the table live; sorting works;
      duplicate rows merge; details open.
- [ ] The Playlists column is compact by default, can be widened by dragging its edge, and a
      song's Details window shows the full playlist list.
- [ ] Find Duplicates in Selection works (songs across the *selected* playlists — distinct from
      the per-playlist "Remove repeated songs" action in section F).
- [ ] Update Selected Playlists refreshes only the selected playlists, and its progress window
      renders normally (title / status / bar / Cancel laid out horizontally, not as vertical text).

## B. Temporary-playlist lifecycle (release build)

> Needs at least one temporary playlist to exist. Create one via "Play in YouTube Music"
> (section D), then run these in a normal `python3 main.py`.

- [ ] Settings shows a "Temporary Playlists" section with the correct count.
- [ ] "View Temporary Playlists" lists title, created timestamp, relative age, and merged-from
      sources.
- [ ] Double-click / Open Selected opens the playlist on music.youtube.com.
- [ ] Delete Selected removes only the chosen rows; the list and count refresh.
- [ ] Delete All prompts, then clears the list.
- [ ] Closing the app with temp playlists present shows the exit dialog:
  - [ ] Cancel aborts the close.
  - [ ] Keep and Close closes without deleting; playlists remain.
  - [ ] Delete and Close deletes (progress shown), then closes.
  - [ ] Checkbox "always delete on exit" + Delete persists the preference
        (re-open Settings: checkbox stays ticked; `app_settings.json` updated).
- [ ] With the preference on, closing deletes silently with no prompt.
- [ ] Relaunch with leftover temp playlists and the preference OFF → startup reminder appears
      (~3.5s after launch) and lists them.
- [ ] Exit deletion with missing/expired headers → warns and still closes (does not hang;
      the 20s safety timeout never traps the app).

## C. Single-instance lock

- [ ] Launch a second instance while the first is running → "already running" warning; the
      second instance exits.
- [ ] Quit the first instance, relaunch → starts normally (lock released).

## D. YouTube Music queue creation (release build)

- [ ] "Play in YouTube Music" is visible in the sidebar without any debug flag.
- [ ] Settings > Set Queue Headers shows the numbered guide; paste Chrome "Copy as fetch
      (Node.js)" output → saved.
- [ ] Test Saved Headers succeeds.
- [ ] Clicking "Play in YouTube Music" with no headers set offers to open the header setup.
- [ ] Select YouTube playlists → Play in YouTube Music → temporary playlist is created, opened,
      and remembered for cleanup.
- [ ] A song that appears in two selected playlists is added once (not reported as skipped).
- [ ] The "Skipped N songs" message (when present) includes a reason summary.
- [ ] Invalid / expired headers → creation fails with a prompt to refresh headers.

## F. Editing your YouTube playlists (account writes)

> Needs fresh queue headers (Settings > Set Queue Headers) **and a playlist you own** — editing
> uses `setVideoId`, which YouTube only returns for your own playlists. Optimistic UI: changes
> show immediately and persist on success; only the Remove confirmation and errors pop up.

- [ ] **Add a song:** right-click a song in View Songs → "Add to playlist" → pick one. The song
      appears on music.youtube.com, and the target playlist's "(N songs)" in the left sidebar
      updates immediately (no flicker, no scroll reset, selection preserved).
- [ ] **Remove a song:** open a song's Details → "In playlist" → Remove (confirms first). Removed
      on YouTube; counts update live.
- [ ] The same add/remove right-click menu works in the **duplicates** list.
- [ ] **Remove repeated songs:** on an owned playlist with a song listed twice, right-click it (or
      use its Details) → "Remove repeated songs" → keeps one, reports "Removed N…", and the Cached
      Tracks / sidebar counts update live; the Details window reopens with fresh counts.
- [ ] **Bulk:** select several songs (shift / ⌘-click) → right-click → "Add N songs to playlist"
      / "Remove N songs from playlist" → the batch is applied in one go.
- [ ] **Create playlist:** select songs → right-click → "New playlist from … song(s)…" → name it
      → a new playlist is created on music.youtube.com and appears in the app's sidebar with the
      right count. Also try the sidebar "Create Playlist from Selected" (merges selected playlists).
- [ ] **Not-owned playlist:** an edit on a playlist you don't own says "you can only edit
      playlists you own."
- [ ] **Stale session:** with expired/logged-out headers, an edit **prompts to refresh headers**
      (not a silent no-op), and Test Saved Headers **fails** rather than falsely reporting "worked."
- [ ] **Pre-flight session check (no startup popup):** with expired headers, clicking "Play in
      YouTube Music" or "Create Playlist" prompts to refresh **immediately** (a quick check up
      front) instead of building for several seconds and then failing. Launch itself shows no popup.
- [ ] **Ownership awareness:** with a valid signed-in session, a playlist you DON'T own shows
      "Owned by you: No" in its Details, its "Remove repeated songs" is disabled, and it doesn't
      appear as an "Add to playlist" target. A playlist you own shows "Owned by you: Yes" and is
      fully editable. (Ownership is detected shortly after launch.)

## G. Custom names, export, removed-songs archive (local; no account)

- [ ] **Custom name:** right-click a song (or use Details) → set one. It shows in the Custom Name
      column and the Search box matches it; the real title stays in Details.
- [ ] Settings "Replace song titles with custom names in lists" swaps the alias for the title in
      the lists and hides the Custom Name column.
- [ ] **Export:** a playlist's Details (or right-click) → "Export…" writes a CSV of
      title/artist/source/id.
- [ ] **Removed-songs archive:** after Update Selected Playlists, any song removed from a playlist
      shows in that playlist's Details under "Removed Songs" (title + artist + relative date), and
      the update-complete dialog reports how many were saved.

## E. Regression check (embedded player removed)

- [ ] There is no "Play Queue" / "Play YouTube Queue" button anywhere and no "Playback" column.
- [ ] A plain run with no temp playlists shows no exit prompt and no startup reminder.
