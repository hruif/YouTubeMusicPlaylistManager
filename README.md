# YouTube Music Public Playlist Manager

YouTube Music for some reason removes the functionality of being able to easily see which playlists a song/video is a part of. Had to put something together to save myself 10 hours when fixing my playlists - fully vibe-coded.

Only relatively basic functionality currently. You can search through playlists and get various info. Streaming the music to a web player directly doesn't seem to work due to no official YouTube Music API. Trying to get a workaround to more conveniently make queues.

Project download page: https://hruif.github.io/YouTubeMusicPlaylistManager/

## Features

- **Add YouTube Playlists**: Import any public YouTube Music playlist by URL
- **Add Spotify Playlists**: Import public Spotify playlists by URL using SpotAPI
- **Persistent Storage**: Playlists are automatically saved and loaded between sessions
- **Display Pane**: Use the right side to show saved playlists, duplicate results, settings, or a combined song table
- **Playlist Info**: Double-click saved playlists to inspect source, IDs, cache stats, and playlist links
- **Live Combined Song View**: Select playlists in the sidebar and browse their combined songs in a sortable table
- **Selected Duplicate Finder**: Find songs that appear more than once in the selected playlist set, including repeats inside a single playlist
- **Song Details and Playback Links**: Open full playlist-occurrence details and launch YouTube Music or Spotify links for playable tracks
- **Edit YouTube Playlists**: Right-click a song (or use its Details window) to add it to another YouTube Music playlist or remove it from one — the change is made on your real account. Requires queue headers (Settings > Set Queue Headers); YouTube only.
- **Search box**: Each display (View Songs, duplicates, saved playlists) has a Search box that filters the list instantly as you type; press Ctrl+F to jump to it. Select all playlists in the sidebar to search your whole library in View Songs.
- **Display Window Mode**: Use Settings to send display output to separate windows and keep playlist selection on the right side
- **Source Logos**: Spotify and YouTube playlists are shown with bundled app-style logo assets for easy differentiation
- **App Updates**: Check GitHub Releases on startup and from Settings, then open the download page when a newer version is available

## Usage

1. **Run the app**:
   ```bash
   python main.py
   ```

2. **Add playlists**:
   - Click "Add Playlist" to add a public YouTube Music or Spotify playlist
   - The app detects the playlist source from the URL
   - Paste the playlist URL and the playlist name and songs are automatically saved

3. **Search songs**:
   - Open "View Songs" and type in its Search box to filter the combined list as you type (Ctrl+F focuses it)
   - Select all playlists in the sidebar to search your whole library; the Playlists column shows which playlists contain each song
   - Right-click a result to add it to another YouTube playlist or remove it (see "Edit YouTube Playlists")

4. **View saved playlists**:
   - Click "View Saved Playlists" to see all saved playlists
   - The right display shows playlist names, sources, IDs, song counts, and cached track counts
   - Double-click a playlist, or select one and click "Details", to open its info panel

5. **View songs** (the default view on launch):
   - "View Songs" is the primary sidebar button and the page the app opens to. It shows the
     combined songs of the selected playlists and updates live as you change the selection.
   - Use the playlist checkboxes in the left sidebar, or the right-side playlist display when display window mode is enabled
   - The song table updates as playlists are selected or deselected
   - Sort by title, artist, playlist, source, or original playlist order
   - Repeated songs are merged into one row with playlist occurrences shown in the table
   - The Playlists column is compact by default; drag its edge to widen it, or open a song's Details for the full, untruncated list
   - Select a song and click "Details" or double-click the row to see the full occurrence list
   - Select a song and click "Play" to launch YouTube or Spotify links externally
   - Open Settings and enable "Open display output in separate windows" if you prefer display output outside the main window

6. **Find duplicates in selected playlists**:
   - Select at least one playlist
   - Click "Find Duplicates in Selection"
   - Results use the right display or a pop-up window, depending on the display setting
   - The playlists column uses source-prefixed labels such as "YouTube: Favorites" and repeats labels when a song appears more than once in a playlist
   - Use Ctrl+F to search within the displayed results

7. **Update playlists**:
   - Select playlists in the sidebar, or the right-side playlist display when display window mode is enabled
   - Click "Update Selected Playlists" to refresh only those playlists

8. **Play selected YouTube playlists in YouTube Music** (experimental):
   - This is a workaround, not real playback. Because there is no official YouTube Music
     streaming API, the app creates a private temporary playlist from your selection and opens
     it on the official YouTube Music site, where you play it.
   - One-time setup: open Settings, click "Set Queue Headers", and follow the numbered steps to
     paste your YouTube Music browser headers (Chrome/Edge: "Copy as fetch (Node.js)"; Firefox:
     "Copy Value" → "Copy Request Headers").
     Click "Test Saved Headers" to confirm. You only repeat this if it stops working (e.g. after
     signing out). The headers stay on your computer.
   - Select one or more YouTube Music playlists, then click "Play in YouTube Music" in the sidebar.
     The first time, the app offers to open the header setup for you.
   - The app creates a private temporary playlist, opens it on music.youtube.com, and remembers it
     for cleanup. Songs that YouTube Music rejects (deleted, private, or region-locked tracks) are
     skipped and reported; duplicates across playlists are merged automatically.
   - Spotify playlists are skipped for this flow for now.

9. **Manage temporary playlists**:
   - Open Settings and click "View Temporary Playlists" to see each temporary playlist's title, when it was created (so you can tell how out of date it is), and which playlists it was merged from. Open or delete individual playlists, or use "Delete All".
   - When you close the app, it offers to delete any leftover temporary playlists. Tick "Always delete temporary playlists when I close the app" to make this automatic; the preference is saved in `app_settings.json`.
   - If you skip cleanup, the app reminds you about leftover temporary playlists shortly after the next launch.
   - Only one copy of the app runs at a time so two windows cannot race while creating, adding to, or deleting temporary playlists.

10. **Check for app updates**:
   - The app checks for newer GitHub Releases shortly after startup
   - Open Settings and click "Check for Updates" to check manually
   - If an update is available, the app prompts before opening the release download page

## Data Storage

When running from source, your playlists and `app_settings.json` (which remembers preferences such as "always delete temporary playlists on exit") are stored in a gitignored `data/` folder in the repo. In the packaged macOS app, everything lives in `~/Library/Application Support/YouTube Music Playlist Manager/` (the debug build uses a separate `… (Debug)` folder).

These files always live in the operating system's application-support folder (never in the repository), and enforce the single-instance guard / hold YouTube Music auth + temporary-playlist cleanup records:

- `instance.lock`
- `ytmusic_oauth_client.json`
- `ytmusic_oauth_token.json`
- `ytmusic_browser_auth.json`
- `temporary_youtube_playlists.json`

The playlist file uses the following format:
```json
{
  "youtube:PLAYLIST_ID": {
    "source": "youtube",
    "id": "PLAYLIST_ID",
    "name": "Playlist Name",
    "videos": ["videoId1", "videoId2"],
    "tracks": [
      {
        "id": "videoId1",
        "videoId": "videoId1",
        "title": "Song Title",
        "artist": "Artist Name",
        "source": "youtube",
        "queueStatus": "Queue OK",
        "queuePlayable": true
      }
    ]
  }
}
```

Spotify playlists use the same shape with a `spotify:PLAYLIST_ID` key and `trackId` values.

## Requirements

- Python 3.10+
- ytmusicapi
- tkinter (built-in with Python)
- spotapi (optional, for public Spotify playlist support)

## Installation

```bash
pip install ytmusicapi
python main.py
```

The "Play in YouTube Music" temporary-playlist feature is available in the normal app (set it up via Settings > Set Queue Headers). It uses ytmusicapi browser-header auth rather than the official YouTube Data API, so there is no quota, but the copied browser headers must be refreshed when Google changes or expires the session.

## Build a macOS app

Install build dependencies, then run the build script:

```bash
python -m pip install -r requirements-build.txt
python tools/build_macos_app.py
```

The script creates:

- `dist/YouTube Music Playlist Manager.app`
- `dist/YouTubeMusicPlaylistManager-0.4.0-macOS.zip`

Attach the zip file to a GitHub Release so the built-in update checker can find it. The app bundle uses the bundled app icon and launches under the name "YouTube Music Playlist Manager" instead of "Python".

## Publish the download page

The static GitHub Pages site lives in `docs/` and is deployed by `.github/workflows/pages.yml`.

After pushing the workflow, open the repository on GitHub and set Pages to deploy from GitHub Actions if it is not already configured. The site will be available at:

```text
https://hruif.github.io/YouTubeMusicPlaylistManager/
```

The page links to GitHub Releases for downloads instead of storing app binaries in the repository. Upload `dist/YouTubeMusicPlaylistManager-0.4.0-macOS.zip` or the current versioned zip to a GitHub Release when you want users to download the app.

## Optional Spotify support

To use Spotify playlist import, install `spotapi`:

```bash
pip install spotapi
```

Then run:

```bash
python main.py
```

> Note: `spotapi` fetches public Spotify playlist information without requiring Spotify Web API credentials. Review the library's licensing and usage terms before using it.

## Contributing & development

Working on the project (or handing it off to another person or AI agent)? Start here:

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — development workflow, the debug-first → release
  feature lifecycle, and conventions.
- [`dev-docs/STATUS.md`](dev-docs/STATUS.md) — living board of planned / in-progress / shipped work and known bugs.
- [`dev-docs/MANUAL_TESTING.md`](dev-docs/MANUAL_TESTING.md) — manual test checklists that complement `pytest`.

AI agents and new contributors get a short orientation in
[`dev-docs/HANDOFF.md`](dev-docs/HANDOFF.md).
