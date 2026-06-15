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
- [ ] Search returns songs from saved playlists with playlist occurrences.
- [ ] View Songs: selecting/deselecting playlists updates the table live; sorting works;
      duplicate rows merge; details open.
- [ ] The Playlists column is compact by default, can be widened by dragging its edge, and a
      song's Details window shows the full playlist list.
- [ ] Find Duplicates in Selection works.
- [ ] Update Selected Playlists refreshes only the selected playlists.

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

## E. Regression check (embedded player removed)

- [ ] There is no "Play Queue" / "Play YouTube Queue" button anywhere and no "Playback" column.
- [ ] A plain run with no temp playlists shows no exit prompt and no startup reminder.
