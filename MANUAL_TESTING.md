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

- [ ] Add a public YouTube playlist by URL; songs load and persist after restart.
- [ ] Add a public Spotify playlist by URL (requires `spotapi`).
- [ ] Search returns songs from saved playlists with playlist occurrences.
- [ ] View Combined Songs: sorting works, duplicate rows merge, details open.
- [ ] Find Duplicates in Selection works.
- [ ] Update Selected Playlists refreshes only the selected playlists.

## B. Temporary-playlist lifecycle (release build)

> Needs at least one temporary playlist to exist. Create one first via the debug build
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

## D. YouTube Music queue (debug build)

- [ ] "Play in YouTube Music" and "Queue Headers" appear only with the debug flag.
- [ ] Set Queue Headers: paste Chrome "Copy as fetch (Node.js)" output → saved.
- [ ] Test Saved Headers succeeds.
- [ ] Select YouTube playlists → Play in YouTube Music → temporary playlist is created, opened,
      and remembered for cleanup.
- [ ] Invalid / expired headers → creation fails with a prompt to refresh headers.

## E. Release vs debug parity

- [ ] In a plain `python3 main.py` run, the queue-creation buttons are hidden.
- [ ] In a plain run with no temp playlists, there is no exit prompt and no startup reminder.
