# Contributing & Development Guide

Canonical workflow and conventions for this project. For a short orientation (humans + AI
agents), see `dev-docs/HANDOFF.md`, plus `dev-docs/STATUS.md` (what's in flight).

## TL;DR
- Read `dev-docs/STATUS.md` before starting; update it as part of your change.
- New **user-facing or account-touching** features ship behind the debug gate first,
  then migrate to release once verified. Fixes / refactors / internal safety / tests /
  docs go straight to release.
- Run `pytest -q` before committing and add tests for new pure logic.
- Run the relevant `dev-docs/MANUAL_TESTING.md` checklist before migrating a feature to release
  or cutting a build.
- End AI commit messages with a `Co-Authored-By:` trailer identifying the agent.

## Feature lifecycle: debug-first, then migrate

Stages (mirror these in `dev-docs/STATUS.md`):

1. **Backlog** — planned, not started.
2. **In progress (debug)** — implemented behind the debug gate.
3. **Verified** — passes `pytest` *and* the relevant `dev-docs/MANUAL_TESTING.md` checklist on the
   debug build.
4. **Released** — gate removed; the feature runs in the normal build.

### What "the debug version" means here

There are two independent flags:

- `PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1` — **runtime UI gate**. `_show_youtube_queue_actions()`
  in `app/ui.py` reads it; gated UI (e.g. the queue buttons) only appears when it is set.
  Run from source with the gate on:

  ```bash
  PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python3 main.py
  ```

- `PLAYLIST_MANAGER_BUILD_DEBUG=1` — **build-time flag** read by `YouTubeMusicPlaylistManager.spec`.
  `python tools/build_macos_app.py --debug` builds `… (Debug).app`, which ships a runtime
  hook that turns the UI gate on automatically.

To **gate** a new feature: wrap its entry points in `if self._show_youtube_queue_actions():`
(grep `app/ui.py` for existing examples).

To **migrate** a feature to release (see checklist below): remove the gate, make sure the
tests cover the now-always-on path, run the manual checklist, and move its `dev-docs/STATUS.md` entry
to *Released*.

### When NOT to gate (important nuance)

Do **not** force everything through a debug phase. Gate things that are *user-facing and
not-yet-trusted* — especially anything that writes to a live YouTube Music / Google account,
or adds a new UI surface. The following go **straight to release** (with tests), because
gating them only adds dead flag code:

- bug fixes to already-released features
- internal refactors
- safety / robustness hardening (locks, atomic writes, error handling)
- tests and documentation

When in doubt, gate it.

### Migration checklist (debug → release)

- [ ] `pytest -q` green, with tests covering the always-on behavior.
- [ ] Relevant `dev-docs/MANUAL_TESTING.md` section run and passing on the debug build.
- [ ] Gate (`if self._show_youtube_queue_actions():`) removed from the feature's entry points.
- [ ] Release vs debug parity re-checked (feature now visible in a plain `python3 main.py` run).
- [ ] `README.md` updated if user-facing behavior changed.
- [ ] `dev-docs/STATUS.md` entry moved to *Released*.

## Data locations & single-instance locking (caps & groups)

Where each file lives depends on **how the app runs** — from source, as the release bundle, or as
the debug bundle. Two helpers in `app/app_paths.py` decide this: `user_data_path(...)` returns the
**`data/` folder in the repo** when running from source and the per-user OS dir when frozen;
`private_user_data_path(...)` **always** returns the per-user OS dir (and the debug *bundle* gets
its own `… (Debug)` dir via `PLAYLIST_MANAGER_DEBUG_BUILD`, set by the debug runtime hook).

| File | From-source (`python main.py`) | Release bundle | Debug bundle |
|---|---|---|---|
| `instance.lock` | OS `…/APP_NAME/` | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| OAuth token/client | OS `…/APP_NAME/` | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| queue headers | OS `…/APP_NAME/` | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| temp-playlist records | OS `…/APP_NAME/` | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| `saved_playlists.json` | **`data/`** | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| `app_settings.json` | **`data/`** | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| `custom_song_names.json` | **`data/`** | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| `removed_songs.json` | **`data/`** | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |
| `unmatched_songs.json` | **`data/`** | OS `…/APP_NAME/` | OS `…/APP_NAME (Debug)/` |

### Caps & groups

The single-instance lock (`app/app_lock.py`) lives next to the records it guards
(`private_user_data_path("instance.lock")`). Think of each distinct lock as a **cap of one**:
at most one running instance per lock. Instances that resolve to the same lock form a **group**,
and you can run **at most one instance from each group at a time**.

- **Group A — shared cap of one:** from-source runs **and** the release bundle. They all resolve
  to the `APP_NAME` dir, so they share one lock — launch a second and it's blocked ("already
  running"). The `.app`'s file location (e.g. `dist/` vs `/Applications`) is irrelevant; only
  *frozen vs source* and the debug marker matter.
- **Group B — its own cap of one:** the debug bundle (its `… (Debug)` dir → separate lock).

So the max you can run concurrently is **one from Group A + the Group B (debug) bundle** — e.g. a
`python main.py` session alongside the debug `.app`. Two release copies, or a from-source run plus
the release bundle, collide (same group).

**Two nuances:**

- **From source does not differentiate release vs debug.** The debug flag
  (`PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1`) changes *behavior* (shows gated UI) but **not** the
  data dir or lock — the `… (Debug)` split is gated on `running_from_bundle()`. So a flagged and an
  unflagged source run share one lock (Group A) and can't run together.
- **From-source ≠ release bundle for data.** They share the lock + OS-dir files (OAuth, headers,
  temp records) but keep **separate** `saved_playlists.json` / `app_settings.json` (`data/` vs OS
  dir), so they coordinate on instances/account data yet show different saved-playlist lists.

## Project layout

- **Root:** only `main.py` (the entry point the `.spec` builds from and `python3 main.py` runs),
  the root docs (`README.md`, `CONTRIBUTING.md`), and config (`pytest.ini`, the `.spec`, etc.).
- **`app/`** — all application code, as a package:
  - `app/ui.py` — the controller.
  - `app/app_info`, `app/app_paths`, `app/app_lock`, `app/app_platform`, `app/app_settings` —
    core/config. `app_paths` anchors the assets dir and the from-source data dir to the **repo
    root** (`Path(__file__).parent.parent`), so they don't move with the package.
  - `app/views/` — Tk screen builders (`*_view.py`), the `playlist_url_window` dialog, and the
    shared `playlist_checkbox_selector`. Each takes the controller as an explicit dependency.
  - `app/services/` — non-Tk logic/state: `playlist_store`, `text_utils`, `playlist_library`
    (saved-playlists state + persistence), `queue_service` (YouTube Music orchestration),
    `playlist_editor` (add/remove songs on the user's YouTube playlists),
    `custom_names` (local per-song aliases), `removed_songs` (archive of songs dropped on
    update) + `playlist_export` (CSV snapshot), `spotify_matcher` (conservative Spotify→YouTube
    track matching) + `unmatched_songs` (per-playlist record of unmatched transfer songs),
    `youtube_music_account`, `update_checker`.
- **`tests/`** — all `test_*.py` (`pytest.ini` sets `pythonpath=.` + `testpaths=tests`).
- **`dev-docs/`** — `STATUS.md`, `MANUAL_TESTING.md`. **`docs/`** is the published GitHub Pages
  site (do not put dev docs there).
- Imports are package-qualified: `from app.views import …`, `from app.services import …`,
  `from app.app_paths import …`. `main.py` imports `from app.ui import …`.

## Testing

- **Automated:** `pytest -q`. Add or extend tests for any new pure logic. GUI/Tk code is not
  unit-tested — factor logic into non-Tk helpers and test those (see `tests/test_ui_helpers.py`
  for the `make_manager()` pattern that builds the controller without a Tk root).
- **Manual:** `dev-docs/MANUAL_TESTING.md` has per-area checklists for the parts `pytest` can't cover.

## Tracking work: dev-docs/STATUS.md vs GitHub Issues

- **`dev-docs/STATUS.md` (in-repo) is the source of truth for the development backlog and in-flight
  work.** It travels with the code, so any agent or person reading the repo sees it in context
  without extra tooling. Update it in the same change that does the work.
- **GitHub Issues are reserved for user-reported bugs / external feedback.** Cross-link to
  `dev-docs/STATUS.md` items when useful.

## Conventions

- **Data & auth files:** see the README "Data Storage" section. Never commit auth/token files.
- **Releases & download page:** see the README "Build a macOS app" / "Publish the download page".
- **Dev docs location:** keep development docs at the repo root. Do **not** put them in `docs/` —
  that folder is the published GitHub Pages site (`.github/workflows/pages.yml` uploads all of it).
- **Handoffs:** prefer updating `dev-docs/STATUS.md` over leaving throwaway handoff files.
- **Commit messages:** end AI-authored commits with a `Co-Authored-By:` trailer identifying the
  agent.
