# YouTube Music Public Playlist Manager

YouTube Music for some reason removes the functionality of being able to easily see which playlists a song/video is a part of. Had to put something together to save myself 10 hours when fixing my playlists - fully vibe-coded.

Only basic functionality currently. Searching for songs reveals which playlists they are in. You can also combine selected playlists and find duplicates within the current selection.

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

## Usage

1. **Run the app**:
   ```bash
   python main.py
   ```

2. **Add playlists**:
   - Click "Add YouTube Playlist URL" to add a public YouTube Music playlist
   - Click "Add Spotify Playlist URL" to add a public Spotify playlist using SpotAPI
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
   - The Playback column marks known YouTube Music-only tracks, which are skipped when building a queue
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

## Data Storage

Playlists are stored in `saved_playlists.json` in the following format:
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

The experimental bulk YouTube queue buttons are hidden by default because most YouTube Music tracks cannot play through the official embed player. To test them manually, run the app with:

```bash
PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS=1 python main.py
```

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
