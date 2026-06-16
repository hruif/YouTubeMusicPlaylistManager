# AGENTS.md

Guide for AI agents (Codex and others) working in this repo. The detailed version is in
`CLAUDE.md` and `CONTRIBUTING.md` — read both before working.

## Read first
- `dev-docs/STATUS.md` — planned / in-progress / shipped work. Update it as part of your change.
- `CONTRIBUTING.md` — full development workflow & conventions.
- `dev-docs/MANUAL_TESTING.md` — manual test checklists.

## Quick rules
- **Debug-first:** new user-facing or account-touching features start behind the
  `PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS` debug gate; migrate to release after verification.
  Fixes, refactors, safety hardening, tests, and docs go straight to release.
- Run `pytest -q` before committing; add tests for new pure logic.
- Run from source with the debug UI: `PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python3 main.py`
- End commit messages with a `Co-Authored-By:` trailer identifying the agent.
- Keep internal dev docs at the repo root, not in `docs/` (that is the published Pages site).
