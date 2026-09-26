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
- `release/mac-universal/YouTube Music Playlist Manager.app`
- `release/YouTube Music Playlist Manager-<version>-universal.dmg`

Packaging is configured in [`electron-builder.yml`](electron-builder.yml). Notable choices:
- **`mac.target: { dmg, arch: universal }`** — one DMG that runs on Apple Silicon **and** Intel.
- **`files` excludes `node_modules`** — the main + preload are esbuild-bundled into `electron-dist/`,
  so nothing from `node_modules` ships at runtime; the asar holds only the bundles + the Vite output.
- **`extraResources`** ships the native `login-helper` outside the asar (a plain executable).
- The Swift helper is compiled **universal** too (`electron/build.mjs` builds arm64 + x86_64 and
  `lipo`s them), so in-app sign-in works on both arches.
- `electronLanguages: en-US` and `compression: maximum` trim the build; even so the `.dmg` is
  ~176 MB — Electron bundles its own Chromium runtime (that's the floor, not app bloat).

## Signing & notarization

Builds are signed with a Developer ID Application certificate (hardened runtime, entitlements in
`build/entitlements.mac.plist`) when one is available, and notarized when Apple credentials are too.
Without them (e.g. CI today) the app is built unsigned, and users approve it once on first launch:

> **System Settings → Privacy & Security → Open Anyway**, or
> `xattr -dr com.apple.quarantine "/Applications/YouTube Music Playlist Manager.app"`, or Control-click → Open.

**Local signed build:**

```bash
CERT_DIR=/path/to/Developer-ID-certs scripts/build-signed-mac.sh               # .app for this Mac → release/mac-<arch>/
CERT_DIR=... APPLE_KEYCHAIN_PROFILE=ytmpm-notary scripts/build-signed-mac.sh --universal   # signed + notarized DMG/zip
```

`CERT_DIR` holds `developerID_application.cer` and its private key (`*.key`). The script puts them
in a throwaway keychain for the build and restores your keychain search list afterwards; your login
keychain isn't modified. (It works around an electron-builder bug in its own `CSC_LINK` import.)

**Notarization credentials** are stored once in your keychain, never in the repo or environment:

```bash
xcrun notarytool store-credentials ytmpm-notary --apple-id you@example.com --team-id Y97FTNGTB8
```

It prompts for an app-specific password (appleid.apple.com → Sign-In and Security → App-Specific
Passwords). Then pass `APPLE_KEYCHAIN_PROFILE=ytmpm-notary` as above.

`--universal` needs full Xcode installed (the Command Line Tools alone can't link the x86_64 slice
of the Swift login helper). The script uses `/Applications/Xcode.app` automatically if it's there.

## Live end-to-end check

`npm run e2e:live` drives the built app (`release/mac-<arch>/`) against your signed-in account to
check undo, feedback and errors for real. It works on a throwaway "zz ytmpm e2e …" playlist copied
from one of your sidebar playlists and deletes it afterwards; your own playlists are only read.
Quit the app first (it runs one copy at a time).

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
  drag/re-approve. It's a custom swap (not Squirrel/electron-updater), kept after signing because
  it already handles the rename and needs no update server. Falls back to the manual `.dmg` if the release has no zip (pre-0.3.4), if not running
  the installed app, or if the install dir needs admin. **Test the in-place path on an actual
  installed copy** before relying on it — it can't run in dev or from the read-only `.dmg` mount.
- **Verified 2026-09-11:** the installed 0.3.4 app downloaded the staged 0.3.5 release ZIP through
  its `installUpdate` bridge, replaced `/Applications/YouTube Music Manager.app`, and relaunched
  as 0.3.5. Settings confirmed the version and signed-in account; the library and selections
  were preserved. This exercised the installed updater before promoting the release to Latest.
- **Verified 2026-09-26:** the real 0.3.5 release (downloaded from GitHub) found the published but
  not-yet-Latest 0.3.6, and **Update & restart** swapped in the notarized 0.3.6 and relaunched it.
  0.3.5's updater keeps the installed bundle's old file name ("YouTube Music Manager.app"); updates
  from 0.3.6 on install under the new name. 0.3.6 was then promoted to Latest.

## Website screenshots

The site's screenshots (`docs/screenshots/`) are the real UI with made-up demo data, so no account
data appears. To retake them after UI changes:

```bash
npm run build && node scripts/screenshots/take.mjs
```

The scenes and demo library are in `scripts/screenshots/` (`take.mjs`, `demo-data.cjs`).
