# YouTube Music Public Playlist Manager

YouTube Music for some reason removes the functionality of being able to easily see which playlists a song/video is a part of. Had to put something together to save myself 10 hours when fixing my playlists - fully vibe-coded.

Only relatively basic functionality currently. You can search through playlists and get various info. Streaming the music to a web player directly doesn't seem to work due to no official YouTube Music API. Trying to get a workaround to more conveniently make queues.

Project download page: https://hruif.github.io/YouTubeMusicPlaylistManager/

## Features

- **Add YouTube Playlists**: Import any public YouTube Music playlist by URL
- **Add Spotify Playlists**: Import public Spotify playlists by URL using SpotAPI
- **Persistent Storage**: Playlists are automatically saved and loaded between sessions
- **Smart Search**: Search for songs and see which of your playlists contain them
- **Display Pane**: Use the right side to show search results, saved playlists, duplicate results, settings, or a combined song table
- **Playlist Info**: Double-click saved playlists to inspect source, IDs, cache stats, and playlist links
- **Live Combined Song View**: Select playlists in the sidebar and browse their combined songs in a sortable table
- **Selected Duplicate Finder**: Find songs that appear more than once in the selected playlist set, including repeats inside a single playlist
- **Song Details and Playback Links**: Open full playlist-occurrence details and launch YouTube Music or Spotify links for playable tracks
- **Display Find**: Press Ctrl+F to search within the active display
- **Display Window Mode**: Use Settings to send display output to separate windows and keep playlist selection on the right side
- **Source Logos**: Spotify and YouTube playlists are shown with bundled app-style logo assets for easy differentiation
- **App Updates**: Check GitHub Releases on startup and from Settings, then open the download page when a newer version is available

## Usage

1. **Run the app**:
   ```bash
   python main.py
   ```

2. **Add playlists**:
   - Click "Add Playlist URL" to add a public YouTube Music or Spotify playlist
   - The app detects the playlist source from the URL
   - Paste the playlist URL and the playlist name and songs are automatically saved

3. **Search songs**:
   - Type a song name in the search bar
   - Only songs from your saved playlists will appear
   - Results show which playlists contain each song

4. **View saved playlists**:
   - Click "View Saved Playlists" to see all saved playlists
   - The right display shows playlist names, sources, IDs, song counts, and cached track counts
   - Double-click a playlist, or select one and click "Details", to open its info panel

5. **View combined songs**:
   - Click "View Combined Songs"
   - Use the playlist checkboxes in the left sidebar, or the right-side playlist display when display window mode is enabled
   - The song table on the right updates as playlists are selected or deselected
   - Sort by title, artist, playlist, source, or original playlist order
   - Repeated songs are merged into one row with playlist occurrences shown in the table
   - Select a song and click "Details" or double-click the row to see the full occurrence list
   - Select a song and click "Play" to launch YouTube or Spotify links externally
   - When the experimental local queue toggle is enabled, the Playback column marks tracks that cannot play in the embedded test player
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

8. **Play selected YouTube playlists in YouTube Music** (experimental, hidden by default):
   - Known limitation: this queue workaround is fragile. The local embedded player cannot
     reliably stream YouTube Music tracks, so the app instead tries to create a private
     temporary playlist and open it on the official YouTube Music site. The "Play in YouTube Music"
     button is hidden unless you launch the app with `PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1`
     (see Installation), and is intended for debugging.
   - In the debug app, click "Queue Headers" in the sidebar, or open Settings and choose "Set Queue Headers"
   - Open music.youtube.com while signed in, copy a logged-in POST `/browse` request in browser developer tools, and paste it into the app. In Chrome, "Copy as fetch (Node.js)" can be pasted directly.
   - Use "Test Saved Headers" before trying to create a queue
   - Select one or more YouTube Music playlists
   - Click "Play in YouTube Music"
   - The app creates a private temporary playlist, opens it on music.youtube.com, and remembers it for cleanup
   - Spotify playlists are skipped for this flow for now

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

When running from source, playlists and `app_settings.json` (which remembers preferences such as "always delete temporary playlists on exit") are stored next to the code. A short-lived `instance.lock` file in the same folder enforces the single-instance guard. In the packaged macOS app, these live in `~/Library/Application Support/YouTube Music Playlist Manager/`.

YouTube Music auth files and temporary playlist cleanup records are stored in the operating system's application-support folder, not in the repository:

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

Install `pywebview` with the same Python interpreter that runs the app if you want the YouTube queue player to open in its own native window instead of a browser tab:

```bash
python -m pip install pywebview
```

The experimental YouTube queue actions — including the "Play in YouTube Music" button and the bulk queue buttons — are hidden by default because most YouTube Music tracks cannot play through the official embed player or temporary-queue workaround. They are debug-only. Temporary playlist creation uses ytmusicapi browser-header auth rather than the official YouTube Data API, avoiding quota usage but requiring fresh copied browser headers when Google changes or expires the session. To show the actions manually, run the app with:

```bash
PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python main.py
```

## Build a macOS app

Install build dependencies, then run the build script:

```bash
python -m pip install -r requirements-build.txt
python tools/build_macos_app.py
```

The script creates:

- `dist/YouTube Music Playlist Manager.app`
- `dist/YouTubeMusicPlaylistManager-0.2.0-macOS.zip`

Attach the zip file to a GitHub Release so the built-in update checker can find it. The app bundle uses the bundled app icon and launches under the name "YouTube Music Playlist Manager" instead of "Python".

## Publish the download page

The static GitHub Pages site lives in `docs/` and is deployed by `.github/workflows/pages.yml`.

After pushing the workflow, open the repository on GitHub and set Pages to deploy from GitHub Actions if it is not already configured. The site will be available at:

```text
https://hruif.github.io/YouTubeMusicPlaylistManager/
```

The page links to GitHub Releases for downloads instead of storing app binaries in the repository. Upload `dist/YouTubeMusicPlaylistManager-0.2.0-macOS.zip` or the current versioned zip to a GitHub Release when you want users to download the app.

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
- [`STATUS.md`](STATUS.md) — living board of planned / in-progress / shipped work and known bugs.
- [`MANUAL_TESTING.md`](MANUAL_TESTING.md) — manual test checklists that complement `pytest`.

AI agents are pointed to the same material via [`CLAUDE.md`](CLAUDE.md) and
[`AGENTS.md`](AGENTS.md).
