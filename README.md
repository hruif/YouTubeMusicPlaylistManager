# YouTube Music Public Playlist Manager

YouTube Music for some reason removes the functionality of being able to easily see which playlists a song/video is a part of. Had to put something together to save myself 10 hours when fixing my playlists - fully vibe-coded.

Only basic functionality currently. Searching for songs reveals which playlists they are in. You can also display all songs in more than one playlist.

## Features

- **Add YouTube Playlists**: Import any public YouTube Music playlist by URL
- **Add Spotify Playlists**: Import public Spotify playlists by URL using SpotAPI
- **Persistent Storage**: Playlists are automatically saved and loaded between sessions
- **Smart Search**: Search for songs and see which of your playlists contain them
- **Source Icons**: Spotify and YouTube playlists are shown with different icons for easy differentiation

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
   - Shows playlist names, IDs, and song counts

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
        "source": "youtube"
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
