# Building & packaging the desktop (Electron) app

## Develop
```bash
cd desktop
npm install
npm run electron:dev      # bundles main/preload (esbuild) + the Swift login-helper, starts Vite,
                          # then launches Electron pointed at the dev server
```
No Rust needed. macOS builds the native login-helper with `swiftc` (Xcode command-line tools).

## Production build
```bash
cd desktop
npm run electron:build    # vite build → bundle main/preload + helper → electron-builder
```
Artifacts land in `release/`:
- `release/mac-universal/YouTube Music Manager.app`
- `release/YouTube Music Manager-<version>-universal.dmg`

Packaging is configured in [`electron-builder.yml`](electron-builder.yml). Notable choices:
- **`mac.target: { dmg, arch: universal }`** — one DMG that runs on Apple Silicon **and** Intel.
- **`files` excludes `node_modules`** — the main + preload are esbuild-bundled into `electron-dist/`,
  so nothing from `node_modules` ships at runtime; the asar holds only the bundles + the Vite output.
- **`extraResources`** ships the native `login-helper` outside the asar (a plain executable).
- The Swift helper is compiled **universal** too (`electron/build.mjs` builds arm64 + x86_64 and
  `lipo`s them), so in-app sign-in works on both arches.
- `electronLanguages: en-US` and `compression: maximum` trim the build; even so the `.dmg` is
  ~176 MB — Electron bundles its own Chromium runtime (that's the floor, not app bloat).

## Signing & notarization (current state)

The build is **unsigned** (`mac.identity: null`) — so a downloaded copy is blocked by Gatekeeper on
first launch. Users approve it once:

> **System Settings → Privacy & Security → Open Anyway**, or
> `xattr -dr com.apple.quarantine "/Applications/YouTube Music Manager.app"`, or Control-click → Open.

**To notarize** (removes the Gatekeeper prompt) you need a **paid Apple Developer ID** — the project
has never had one, which is why neither app is notarized. With a Developer ID, set a signing identity
in `electron-builder.yml` (`mac.identity`) and configure electron-builder notarization
(`mac.notarize`, or an `afterSign` notarize hook with `APPLE_ID` / `APPLE_APP_SPECIFIC_PASSWORD` /
`APPLE_TEAM_ID` in the environment). It's purely credentials + config — no app code change.

## Distribution / updates

- `npm run electron:build` produces **two** mac artifacts in `release/` (see `electron-builder.yml`
  `mac.target`): the `…-universal.dmg` (the download) **and** a `…-universal-mac.zip` (the zipped
  `.app` the in-app updater swaps in place). **Attach both** to every release.
- The GitHub Pages site (`docs/`) and `releases/latest` point at the `.dmg`; the download button
  resolves the latest release's `.dmg`.
- Cut a release with both assets:
  ```bash
  gh release create desktop-v<version> \
    "release/…-universal.dmg" "release/…-universal-mac.zip" --target main --latest
  ```
- **In-app updates (`electron/updater.ts`).** The checker compares the running version against the
  latest non-prerelease `desktop-v*` release. When running the packaged app on a release that ships
  the `…-mac.zip`, the banner/Settings offer **"Update & restart"**: it downloads the zip, strips the
  Gatekeeper quarantine, and a detached helper swaps the bundle in place + relaunches — no
  drag/re-approve. Unsigned, so this is a custom swap (not Squirrel/electron-updater, which need a
  Developer ID). Falls back to the manual `.dmg` if the release has no zip (pre-0.3.4), if not running
  the installed app, or if the install dir needs admin. **Test the in-place path on an actual
  installed copy** before relying on it — it can't run in dev or from the read-only `.dmg` mount.
