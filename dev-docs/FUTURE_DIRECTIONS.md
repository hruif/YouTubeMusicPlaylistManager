# Future Directions — UI Revamp, Auth, and Delivery

_Status: planning only — no rewrite code written yet._
_Last updated: 2026-06-17._

Scoping document for where the app could go next. Two motivating goals, three possible delivery
forms, and a **shared-core architecture** that keeps both directions open without committing to
either up front. Supersedes the earlier Tauri-only plan.

The Python/Tkinter app **keeps shipping** until any successor reaches feature parity.

## Goals

1. **Improve the UI.** The current Tkinter UI is barebases and functional but visually basic;
   the goal is a genuinely cleaner, more modern UI. A *native-macOS look is not a hard
   requirement* — "clean and modern" is enough, which widens the options (any web-based UI clears
   Tkinter's ceiling). (The JustAnotherMusicClient app was only an *example* of clean UI, not a
   reference to copy.)
2. **Reduce auth friction.** Today the user manually copies a *frozen* header snapshot from an
   external browser; Google rotates the session cookies (~hourly) and it dies. We want a model
   where the session stays fresh on its own.

## Shared-core architecture (the recommended foundation)

Whatever the frontend(s), structure the code so the brains are written once and either delivery
form is cheap to add later:

- **`packages/core` (shared TypeScript):** platform-agnostic logic — data models, Spotify→YT
  matching, dedup, in-playlist repeat detection, unavailable-track categorization, custom-names
  and removed-songs logic, CSV export. (Ports of the Python `services/*` algorithms, which already
  have test coverage.)
- **`packages/ui` (shared React):** the components — song table, sidebar, details, dialogs,
  settings — reused by either frontend.
- **Per-platform adapters (the part that genuinely differs):** a small data/auth layer behind a
  common interface, so the core/UI don't care which is in use.

This makes "do both eventually" realistic: the second frontend is a new adapter + shell, not a
second rewrite.

## Delivery options

### Option A — Chrome (Chromium) extension
- **Auth:** runs **inside the browser on `music.youtube.com`**, in your already-logged-in, always
  fresh session. The browser attaches your session cookies (incl. `httpOnly`) to same-origin
  requests automatically. The cleanest implementation injects into the page's MAIN world and
  reuses the page's own authenticated request context. **The manual-header problem essentially
  disappears** — nothing to copy, store, or refresh.
- **Data/adapter:** issues the same InnerTube calls the YT Music web app makes. Local data in
  `chrome.storage` / IndexedDB. Spotify import works from the MV3 service worker via
  `host_permissions` (Spotify Web API client-credentials, or scraping public playlists).
- **UI:** popup, **Side Panel** (Chrome Side Panel API), injected-into-page, or a full-page
  extension tab. Can look clean/modern; not a standalone native window.
- **Cross-platform for free:** any Chromium browser on any OS. **No PyInstaller / Tauri / code
  signing / notarization** — the biggest packaging headaches vanish.
- **Distribution catch:** the Chrome Web Store **reviews** extensions and Google can **delist**
  one unilaterally (see Risk). Self-hosting (unpacked / `.crx`) avoids the store at the cost of
  easy installs.

### Option B — Tauri desktop app (Rust + web frontend)
- **Auth:** embed a native WebView sign-in (WKWebView on macOS) like JustAnotherMusicClient — a
  persistent, app-owned login session that yields fresh cookies. Their auth code is **Apache-2.0**
  and can be adapted directly (keep notices + ship a `NOTICE` file). The native WebView cookie
  store *can* read `httpOnly` cookies (it's the app's own webview, not page JS) — which is why
  this works where the rejected bookmarklet / "read the external browser's store" (Option B in
  STATUS) ideas didn't, and it carries none of that Keychain trust problem.
- **Data/adapter:** `youtubei.js` (InnerTube) through a Rust HTTP proxy. Filesystem storage.
- **UI:** a real standalone window; the closest to a "native app" feel.
- **Distribution:** you ship it yourself — **no store gatekeeper** (but no one-click install for
  non-technical users either). Tauri's signing/notarization is nicer than the current PyInstaller
  + `ditto` workaround.

### Option C — keep Python, just theme the UI (baseline)
- Lowest effort, but Tkinter's ceiling is low; it won't reach "modern," and it doesn't touch the
  auth problem. Reasonable as a stopgap, not the destination.

### Option D — PySide6 (Qt) + QtWebEngine (Python, considered & rejected for the product goal)
- Would keep the entire Python core (services, tests, `spotapi`) and replace only the Tkinter UI
  with Qt, with embedded-webview auth via QtWebEngine. **Least effort** by far — but the decision
  was made on *best product*, not effort, and on that axis Tauri wins (see "Tauri vs Qt" below).

## Decision: Tauri vs Qt (best-product lens, effort/reuse discounted)

Chosen: **Tauri.** They are *not* balanced — Tauri has real advantages for this specific app:

1. **Auth robustness (decisive).** The product hinges on an embedded-webview login slipping past
   Google's "This browser or app may not be secure" block on embedded webviews (enforced since
   Sept 2021, and documented to hit **Electron and QtWebEngine**). On macOS, Tauri uses
   **WKWebView — literally Safari's engine** — so a Safari user-agent is nearly indistinguishable
   from real Safari and passes (this is exactly why JustAnotherMusicClient works). **Qt's
   QtWebEngine is embedded Chromium**, which Google fingerprints and blocks, with only flaky
   UA-spoof workarounds. Tauri-on-macOS is the demonstrated-working path; Qt is the more likely to
   be blocked. (Caveat: on Windows Tauri uses Chromium-based WebView2 and loses this edge — so it's
   a macOS-specific advantage, which suits this macOS-first app.)
2. **Footprint.** Tauri uses the *system* WebView for UI + login → tiny binary. Qt must **bundle a
   full Chromium (QtWebEngine) just for the login window** (~150MB), shipped regardless — heavier
   than Tauri's whole architecture.
3. **UI ceiling + ecosystem.** Web/CSS/React has the highest ceiling for a modern, custom UI and a
   far larger component/tooling ecosystem. QML is capable but smaller; Qt Widgets is native but
   utilitarian. We want modern/clean, not native-widgets → web wins.
4. **Distribution.** Tauri has first-class signing/notarization/DMG + a built-in auto-updater;
   Qt + PyInstaller is more manual and QtWebEngine complicates notarization.

Qt's only real wins (native OS controls, single-language reuse, consistent cross-platform
rendering) are exactly the effort/native-feel factors discounted for this decision.

**Caveat bigger than Tauri-vs-Qt:** the *entire* embedded-login premise depends on continuing to
evade Google's block. JustAnotherMusicClient on WKWebView is the best evidence it currently works,
but Google could tighten it. The **only** approach immune to this is the **Chrome extension** (it
rides the real, already-authenticated browser session — no embedded login to detect). Keep it as a
fallback if Google ever blocks the WKWebView path. This makes the **Phase 0 auth spike the first
and most important step** — it validates the riskiest assumption before any UI investment.

## Feature-parity / porting notes (applies to A and B)

The successor must reproduce what the Python app already does (`README.md` + `STATUS.md` are the
spec). By porting difficulty:

- **Ports cleanly:** YT read + add-song; the pure logic/heuristics above (translate to TS, port
  the tests).
- **New / unproven (validate early):** the YT write ops we use that JustAnotherMusicClient does
  *not* — **create playlist, remove-by-`setVideoId`, delete, remove-repeats**. `youtubei.js`
  exposes these but the paths are unexercised in their code; `setVideoId` removal + ownership
  detection is the same gotcha that bit the Python app. **Spotify is the biggest gap** — no clean
  JS equivalent of `spotapi`; needs the Spotify Web API or a scraper (true for both A and B).
- **Local/OS features:** temp-playlist lifecycle, single-instance lock (extension N/A), data-dir
  layout, update checker.

## Phased plan

1. **Phase 0 — Spike (smallest, highest-value).** Prove the auth premise on whichever frontend
   you pick: sign in / use the live session, then do **one real read + one real write (add a
   song)** with no manual headers, plus a smoke-test of a `youtubei.js`/InnerTube **create** and
   **remove-by-`setVideoId`** to retire the biggest unknown. The extension reaches this even
   faster than Tauri (no Rust).
2. **Phase 1 — Read-only parity:** library + combined song view (sort, duplicate-merge, search).
3. **Phase 2 — Edits + ownership:** add/remove/create/remove-repeats; ownership detection;
   optimistic UI with revert; bulk edits.
4. **Phase 3 — Spotify:** public-playlist import + conservative transfer + persisted unmatched list.
5. **Phase 4 — Polish & local features:** custom names, removed-songs archive, export, unavailable
   finder, temp-playlist flow, update checker, packaging.

## Phase 0 — VALIDATED (2026-06-17)

The spike (`desktop/`) confirms the premise end-to-end on macOS:

- **Embedded login works and Google does NOT block it.** A Tauri `WebviewWindow` (WKWebView) with a
  Safari user-agent loads Google sign-in normally; no "browser may not be secure".
- **The session persists across launches** — WKWebView keeps its profile, so a hidden window
  re-captures the session silently on startup (no password, no UI). True no-reauth.
- **Authenticated read + write both work** with the captured cookies via `youtubei.js` 17.0.1
  (account/library read returns the real account's data; writes use `playlist.addVideos` etc.).

Auth gotchas discovered (each cost a debugging round — keep them for the real build):
1. **`Cookie` is stripped by WKWebView.** youtubei.js sets `Cookie` on a WebKit `Headers` object,
   which WKWebView drops as a forbidden header. The Rust proxy must attach the session `Cookie`
   itself for youtube/google hosts.
2. **`Origin` must be set explicitly.** youtubei.js only sets `Origin` on the *server* platform
   (`HTTPClient.js`: `if (Platform.shim.server)`), assuming the browser adds it. Our requests
   bypass the browser, so without a manually-set `Origin` the SAPISIDHASH is unbound and Google
   ignores the auth (response shows `yt_li=0`). Set `Origin`/`Referer` to the origin the hash was
   computed for (`https://www.youtube.com`, or `https://music.youtube.com` for the music client 67,
   where we also recompute the hash).
3. **`SAPISID` may only be present as `__Secure-3PAPISID`** on `.youtube.com` (same value); add a
   `SAPISID=` alias so youtubei.js's auth path finds it.

Open Phase-1 items surfaced by the spike: use the **YT Music-specific library API** (not the
generic `getLibrary()`) to get playlist **names**, the **full** list, and **private** playlists;
and surface the correct account identity.

## Recommended path

Build the **shared core** first, then start with the **Chrome extension** as the first frontend:
it solves the auth pain most directly, has the least build/packaging friction, and a clean
side-panel UI likely satisfies the "not barebones" goal. Add a **Tauri** frontend later from the
same core if a standalone native-feeling app is wanted. Keep the Python app alive until parity.

## Usage tracking (downloads & usage)

How many people download / use the app, in tiers from least to most effort/insight. Dashboards
and counts are **private / for the maintainer** — nothing is shown on the download page.

- **Tier 1 — download counts (active).** `tools/download_stats.py` reads GitHub's per-release
  asset `download_count` from the public API on demand. No app changes, no telemetry, no privacy
  surface. Counts *downloads*, not people (re-downloads / each version / bots all count) and says
  nothing about whether the app is run.
- **Tier 2 — download-page analytics (wired, off by default).** A privacy-friendly, **cookieless,
  no-PII** GoatCounter snippet in `docs/index.html`, plus a download-button click event. It is
  **inert until a code is set** (`GOATCOUNTER_CODE` placeholder) — nothing loads and no request is
  made until you create a free GoatCounter site and fill it in. Dashboard is private by default; no
  consent banner needed. Measures *interest* (visits + download clicks), blocked by some ad
  blockers.
- **Tier 3 — in-app anonymous usage ping (deferred).** The only way to measure real *active*
  usage: a minimal opt-out launch ping (random opaque install ID + app version + coarse OS, no IP
  retention), to a tiny backend (e.g. Cloudflare Worker + KV). Must be disclosed. Not built yet —
  add only once there are real downloads to measure against. Slightly ironic given the app's ToS
  posture, so keep it genuinely minimal and opt-out.

## Legal / ToS posture (all options)

**None of these are ToS-compliant**, and the delivery vehicle doesn't change that. The ToS governs
*how you access the service*, not *which tool* you use; the features here (cross-playlist analysis,
bulk edits, create/delete, transfers) all rely on **programmatic calls to YouTube's internal API**,
i.e. automated access / circumventing the official API. An extension "working within the browser"
is **not** an exception — the browser is merely *capable*; you're still directing automated
requests. (A pure UI-augmentation extension that only reorganizes what the page already rendered
would be much closer to acceptable, but that can't do this app's core features.)

That said, a ToS breach is a **contract matter, not a crime**: own-account access with own
credentials, no DRM/technical-protection circumvention, no ad/Premium bypass, no downloading. So
the realistic exposure is account-level and distribution-level, not legal jeopardy.

### Realistic distribution risk

Google's enforcement ladder, least → most aggressive (most likely outcomes first):

1. **Technical countermeasures** — they change/break the internal API or add bot detection. By far
   the most common "action," and untargeted; breaks every unofficial client equally.
2. **Account-level action** — rate-limit / flag / (rarely) suspend an account doing unusual
   automated activity. Falls on each user; low for personal-volume use.
3. **Web Store delisting (extensions only)** — the cheapest, most likely action against an
   *extension*: pull the listing. Existing installs keep working until they update; self-hosting
   sidesteps it.
4. **DMCA / cease-and-desist** — to the host (e.g. GitHub) or developer if the project gets
   visible. This is the youtube-dl pattern (takedown, later reversed) — aimed at the repo/listing,
   not the person's finances.
5. **Lawsuit against an individual** — extremely rare; reserved for commercial-scale or
   revenue-impacting actors. Not a realistic outcome for a personal, non-commercial playlist tool.

**What raises the profile** (it's not a pure user-count threshold — it's visibility × commercial
impact × annoyance):
- **Monetization** (charging, ads, large-scale donations) — the single biggest escalator.
- **Publicity** (press, going viral, trending repo).
- **API traffic volume** large enough to show up / cost infra.
- **Bypassing ads / Premium / enabling downloads** — draws far more heat than playlist
  organizing. *This app does none of these*, which keeps it well down the threat list (a playlist
  organizer is much less provocative than a downloader like yt-dlp, which is hugely popular and
  still only ever faced a — reversed — takedown, not suits against its maintainers).

**Rough intuition:** a personal, non-commercial tool with tens-to-low-hundreds of users, no press,
doing playlist management, is realistically in the "no one at Google notices or cares" zone. The
inflection comes with **monetization** and/or **real publicity** and/or **thousands of users**, and
even then the first move is a block/takedown, not a courtroom.

### Is "an extension is less of a problem because they can just pull it" right?

**Directionally yes, with a nuance.**
- **Right on severity:** because Google has an easy, proportionate remedy (delist), they're *more
  likely to just use it* and *less likely to escalate* to anything heavier. Lower worst-case.
- **But it's also the easiest channel to kill:** one delisting removes your distribution (existing
  installs persist until update; you can fall back to self-hosting). A self-distributed desktop app
  has **no central kill switch** — Google can't pull it off users' machines; they can only break
  the API.
- So the trade is: **extension = lower escalation risk but a single easy off-switch on
  distribution; standalone app = no off-switch on distribution but slightly more "they'd have to do
  something deliberate" if they ever cared.** In practice, for a tool like this, both are far more
  likely to be broken by an *API change* than by any legal or store action.

**Bottom line:** keep it personal/non-commercial, don't bypass ads/Premium/downloads (it doesn't),
carry the README disclaimer, and the worst realistic case is "the API breaks" or "the extension
gets delisted" — not legal trouble.
