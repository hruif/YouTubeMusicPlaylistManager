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
- **Two coexisting apps:** the original **Python/Tkinter** app at the root (described below), and the
  native **Electron (React/TS)** rewrite in [`desktop/`](../desktop/), now the primary download
  (release `desktop-v0.3.0`, universal `.dmg`). See the **Desktop app** section just below for it;
  the Python-specific rules in the rest of this handoff are for the root app.
- `main.py` (entry point) is the only code file at the root; all application code is under `app/`
  — `app/ui.py` (controller), `app/app_*` (core/config), `app/views/`, `app/services/`.
- Tests live in `tests/` (`pytest -q`). In-repo dev docs live in `dev-docs/`; `docs/` is the
  **published GitHub Pages site** (don't put dev docs there). From-source data lives in `data/`
  (gitignored).

## Desktop app (Electron — now the primary product)
The shipped app is the Electron rewrite in `desktop/`; **its own docs are the source of truth**
(`desktop/README.md`, `desktop/BUILD.md`). Quick orientation:
- **Code:** `desktop/electron/` is the Node main process — `youtubei.js` lives in `yt.ts`, IPC in
  `main.ts`/`backend.ts`, native sign-in in `auth.ts` + `login-helper/`; `desktop/src/` is the React
  renderer (`App.tsx` controller, `lib/`, `components/`).
- **Run/build/test (from `desktop/`):** `npm run electron:dev` (dev), `npm run electron:build`
  (universal `.dmg` via electron-builder, output in `release/`), `npx vitest run` (matcher/cache unit
  tests) + `npx tsc --noEmit`.
- **Sign-in is macOS-only by design:** a native Swift WKWebView helper, because Google blocks
  embedded Chromium. A Linux WebKitGTK port is being validated (`login-helper/login_linux_spike.py`,
  STATUS backlog); Windows would need a manual cookie-paste fallback.
- **Same rules apply:** run the tests/typecheck before committing, end AI commits with the
  `Co-Authored-By:` trailer, and keep `dev-docs/STATUS.md` + the desktop docs in sync with any
  behavior / build / version change. Never commit captured auth/session files.

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
- **Keep the docs in sync — in the same change.** When you alter behavior, UI labels, file
  layout, run/build commands, data locations, or the version, update the docs that describe them:
  `README.md` (user-facing: features/usage/data storage/version), `CONTRIBUTING.md` (workflow +
  project layout + data-location table), and `dev-docs/STATUS.md`. Doc drift is the main risk as
  the project grows — a quick grep for renamed buttons, moved file paths, and old version numbers
  before committing catches most of it.
