# Handoff & Working Guide

Orientation for **humans and AI agents** working in this repo. The detailed conventions live in
`CONTRIBUTING.md` (at the repo root); this file is the short version.

> Note for AI agents: this repo has no root `CLAUDE.md`/`AGENTS.md`, so this guide is **not
> auto-loaded** — read it (and `CONTRIBUTING.md` + `dev-docs/STATUS.md`) at the start of a task.

## Read first
- `dev-docs/STATUS.md` — what's planned / in progress / shipped. **Update it as part of your change.**
- `CONTRIBUTING.md` — full development workflow, conventions, and project layout.
- `dev-docs/MANUAL_TESTING.md` — manual checklist; run the relevant section before migrating a
  feature to release or cutting a build.

## Project layout (quick)
- `main.py` (entry point) is the only code file at the root; all application code is under `app/`
  — `app/ui.py` (controller), `app/app_*` (core/config), `app/views/`, `app/services/`.
- Tests live in `tests/` (`pytest -q`). In-repo dev docs live in `dev-docs/`; `docs/` is the
  **published GitHub Pages site** (don't put dev docs there). From-source data lives in `data/`
  (gitignored).

## For AI agents — must-follow rules
- **Debug-first:** new **user-facing or account-touching** features ship behind the
  `PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS` gate first, then migrate to release once verified. Bug
  fixes, refactors, safety hardening, tests, and docs go **straight to release**. (Mechanics +
  the migration checklist are in `CONTRIBUTING.md`.)
- **Tests:** run `pytest -q` before committing; add tests for new pure logic.
- **Run from source with the debug UI:**
  ```bash
  PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python3 main.py
  ```
- **Commit footer:** end AI-authored commits with a `Co-Authored-By:` trailer identifying the agent.
- Prefer updating `dev-docs/STATUS.md` over leaving throwaway handoff files.
