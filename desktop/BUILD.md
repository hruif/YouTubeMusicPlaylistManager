# Building & packaging the desktop (Tauri) app

## Develop
```bash
cd desktop
npm install
npm run tauri dev      # needs Rust on PATH: source "$HOME/.cargo/env"
```

## Production build
```bash
cd desktop
npm run tauri build
```
Artifacts land in `src-tauri/target/release/bundle/`:
- `macos/YouTube Music Manager.app`
- `dmg/YouTube Music Manager_<version>_<arch>.dmg`

With `--target universal-apple-darwin` (the ship vehicle — see below), the bundle path is instead
`src-tauri/target/universal-apple-darwin/release/bundle/…` and the dmg is suffixed `_universal`.

The bundle is **~12 MB** (the Python app was ~148 MB) — Tauri uses the system WebView
(WKWebView) instead of bundling a browser/runtime.

`--target universal-apple-darwin` builds a universal (Intel + Apple Silicon) binary; a plain build
targets the host arch only (this machine: `aarch64`).

## Signing & notarization (current state)

The build is **ad-hoc signed** (`Signature=adhoc`, `TeamIdentifier=not set`) — i.e. effectively
unsigned, the same as the Python app. So a downloaded copy is blocked by Gatekeeper on first launch;
users approve it the same way as before:

> **System Settings → Privacy & Security → Open Anyway**, or
> `xattr -dr com.apple.quarantine "/Applications/YouTube Music Manager.app"`, or Control-click → Open.

**To notarize** (removes the Gatekeeper prompt) you need a **paid Apple Developer ID** — the project
has never had one, which is why neither app is notarized. With a Developer ID, Tauri notarizes
automatically when these env vars are set for `tauri build`:
- `APPLE_SIGNING_IDENTITY` (or `APPLE_CERTIFICATE` + `APPLE_CERTIFICATE_PASSWORD`)
- `APPLE_ID`, `APPLE_PASSWORD` (app-specific password), `APPLE_TEAM_ID`

See the Tauri macOS code-signing docs. No code change is needed — it's purely credentials + env.

## Distribution / updates

- Ship the `.dmg` (it preserves the signed `.app`; no `ditto`/symlink dance needed like the Python
  zip flow).
- **In-app update checker is deferred** until the Tauri app has its own release line/versioning
  (the repo's current GitHub Releases are the Python app's). When it does, either Tauri's updater
  plugin (needs a signing key + an update manifest) or a simple "check GitHub latest release vs
  `version`" check (like the Python app) can be wired in.
