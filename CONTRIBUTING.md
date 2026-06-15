# Contributing & Development Guide

Canonical workflow and conventions for this project. AI agents: also see `CLAUDE.md`
/ `AGENTS.md` (short, auto-loaded) and `STATUS.md` (what's in flight).

## TL;DR
- Read `STATUS.md` before starting; update it as part of your change.
- New **user-facing or account-touching** features ship behind the debug gate first,
  then migrate to release once verified. Fixes / refactors / internal safety / tests /
  docs go straight to release.
- Run `pytest -q` before committing and add tests for new pure logic.
- Run the relevant `MANUAL_TESTING.md` checklist before migrating a feature to release
  or cutting a build.
- End AI commit messages with a `Co-Authored-By:` trailer identifying the agent.

## Feature lifecycle: debug-first, then migrate

Stages (mirror these in `STATUS.md`):

1. **Backlog** — planned, not started.
2. **In progress (debug)** — implemented behind the debug gate.
3. **Verified** — passes `pytest` *and* the relevant `MANUAL_TESTING.md` checklist on the
   debug build.
4. **Released** — gate removed; the feature runs in the normal build.

### What "the debug version" means here

There are two independent flags:

- `PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1` — **runtime UI gate**. `_show_youtube_queue_actions()`
  in `ui.py` reads it; gated UI (e.g. the queue buttons) only appears when it is set.
  Run from source with the gate on:

  ```bash
  PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python3 main.py
  ```

- `PLAYLIST_MANAGER_BUILD_DEBUG=1` — **build-time flag** read by `YouTubeMusicPlaylistManager.spec`.
  `python tools/build_macos_app.py --debug` builds `… (Debug).app`, which ships a runtime
  hook that turns the UI gate on automatically.

To **gate** a new feature: wrap its entry points in `if self._show_youtube_queue_actions():`
(grep `ui.py` for existing examples).

To **migrate** a feature to release (see checklist below): remove the gate, make sure the
tests cover the now-always-on path, run the manual checklist, and move its `STATUS.md` entry
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
- [ ] Relevant `MANUAL_TESTING.md` section run and passing on the debug build.
- [ ] Gate (`if self._show_youtube_queue_actions():`) removed from the feature's entry points.
- [ ] Release vs debug parity re-checked (feature now visible in a plain `python3 main.py` run).
- [ ] `README.md` updated if user-facing behavior changed.
- [ ] `STATUS.md` entry moved to *Released*.

## Testing

- **Automated:** `pytest -q`. Add or extend tests for any new pure logic. GUI/Tk code is not
  unit-tested — factor logic into non-Tk helpers and test those (see `test_ui_helpers.py` for
  the `make_manager()` pattern that builds the controller without a Tk root).
- **Manual:** `MANUAL_TESTING.md` has per-area checklists for the parts `pytest` can't cover.

## Tracking work: STATUS.md vs GitHub Issues

- **`STATUS.md` (in-repo) is the source of truth for the development backlog and in-flight
  work.** It travels with the code, so any agent or person reading the repo sees it in context
  without extra tooling. Update it in the same change that does the work.
- **GitHub Issues are reserved for user-reported bugs / external feedback.** Cross-link to
  `STATUS.md` items when useful.

## Conventions

- **Data & auth files:** see the README "Data Storage" section. Never commit auth/token files.
- **Releases & download page:** see the README "Build a macOS app" / "Publish the download page".
- **Dev docs location:** keep development docs at the repo root. Do **not** put them in `docs/` —
  that folder is the published GitHub Pages site (`.github/workflows/pages.yml` uploads all of it).
- **Handoffs:** prefer updating `STATUS.md` over leaving throwaway handoff files.
- **Commit messages:** end AI-authored commits with a `Co-Authored-By:` trailer identifying the
  agent.
