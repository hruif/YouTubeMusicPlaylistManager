# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repo. This file is short on
purpose; canonical detail lives in `CONTRIBUTING.md`.

## Read first
- `dev-docs/STATUS.md` — what's planned / in progress / shipped. **Update it as part of your change.**
- `CONTRIBUTING.md` — development workflow & conventions.
- `dev-docs/MANUAL_TESTING.md` — manual checklist; run the relevant section before migrating a feature
  to release.

## Must-follow rules
- **Debug-first:** new **user-facing or account-touching** features ship behind the
  `PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS` gate first, then migrate to release once verified.
  Bug fixes, refactors, safety hardening, tests, and docs go **straight to release**.
  (Mechanics + the migration checklist are in `CONTRIBUTING.md`.)
- **Tests:** run `pytest -q` before committing; add tests for new pure logic.
- **Run from source with the debug UI:**
  ```bash
  PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python3 main.py
  ```
- **Commit footer:** end AI-authored commits with a `Co-Authored-By:` trailer identifying the
  agent.
- **Do not** put internal dev docs in `docs/` — that folder is the published GitHub Pages site.
- Prefer updating `dev-docs/STATUS.md` over leaving throwaway handoff files.
