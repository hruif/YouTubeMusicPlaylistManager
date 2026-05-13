# YouTube Music Public Playlist Manager

YouTube Music for some reason removes the functionality of being able to easily see which playlists a song/video is a part of. Had to put something together to save myself 10 hours when fixing my playlists - fully vibe-coded.

Only basic functionality currently. Searching for songs reveals which playlists they are in. You can also display all songs in more than one playlist.

## Features

- **Add Public Playlists**: Import any public YouTube Music playlist by URL
- **Persistent Storage**: Playlists are automatically saved and loaded between sessions
- **Smart Search**: Search for songs and see which of your playlists contain them
- **No Authentication**: Works with public playlists only (no login required)

## Usage

1. **Run the app**:
   ```bash
   python main.py
   ```

2. **Add playlists**:
   - Click "Add Public Playlist URL"
   - Paste a YouTube Music playlist URL
   - The playlist name and songs are automatically saved

3. **Search songs**:
   - Type a song name in the search bar
   - Only songs from your saved playlists will appear
   - Results show which playlists contain each song

4. **View saved playlists**:
   - Click "View Saved Playlists" to see all saved playlists
   - Shows playlist names, IDs, and song counts

## Data Storage

Playlists are stored in `saved_playlists.json` in the following format:
```json
{
  "PLAYLIST_ID": {
    "name": "Playlist Name",
    "videos": ["videoId1", "videoId2", ...]
  }
}
```

## Requirements

- Python 3.10+
- ytmusicapi
- tkinter (built-in with Python)

## Installation

```bash
pip install ytmusicapi
python main.py
```