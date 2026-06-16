"""Pure, Tk-free playlist identity/key helpers extracted from the UI controller.

These are stateless transforms over playlist/track dicts and storage keys, kept
dependency-free so they can be unit-tested directly. File I/O and the live
``saved_playlists`` state stay in the controller (they are not pure).
"""
import re

# Canonical source -> display-name map. The UI controller aliases its
# ``SOURCE_LABELS`` to this so there is a single source of truth.
SOURCE_LABELS = {
    "youtube": "YouTube",
    "spotify": "Spotify",
}


def normalize_song_key(title, artist):
    combined = f"{title or ''} {artist or ''}".lower()
    combined = re.sub(r"[^\w\s]", "", combined)
    combined = re.sub(r"\s+", " ", combined).strip()
    return combined


def playlist_storage_key(source, playlist_id):
    return f"{source}:{playlist_id}"


def split_storage_key(stored_key, known_sources=SOURCE_LABELS):
    if isinstance(stored_key, str) and ":" in stored_key:
        source, playlist_id = stored_key.split(":", 1)
        if source in known_sources and playlist_id:
            return source, playlist_id
    return "youtube", stored_key


def normalize_playlist_identity(stored_key, pl_data, known_sources=SOURCE_LABELS):
    stored_source, stored_playlist_id = split_storage_key(stored_key, known_sources)

    source = pl_data.get("source") or stored_source
    if source not in known_sources:
        source = stored_source

    playlist_id = pl_data.get("id") or stored_playlist_id
    if isinstance(playlist_id, str) and playlist_id.startswith(f"{source}:"):
        playlist_id = playlist_id.split(":", 1)[1]

    return source, playlist_id


def select_youtube_playlist_sources(saved_playlists, playlist_keys):
    """Split the selected playlist keys into YouTube sources (usable for the queue) and
    skipped non-YouTube sources. Returns (youtube_playlists, skipped_playlists) as lists of
    {key, id, name, source} dicts."""
    youtube_playlists = []
    skipped_playlists = []
    for playlist_key in playlist_keys:
        pl_data = saved_playlists.get(playlist_key)
        if not pl_data:
            continue

        source, playlist_id = normalize_playlist_identity(playlist_key, pl_data)
        playlist_info = {
            "key": playlist_key,
            "id": playlist_id,
            "name": pl_data.get("name", "Unnamed Playlist"),
            "source": source,
        }
        if source == "youtube":
            youtube_playlists.append(playlist_info)
        else:
            skipped_playlists.append(playlist_info)

    return youtube_playlists, skipped_playlists


def combined_track_key(track):
    title = track.get("title", "")
    artist = track.get("artist", "")
    song_key = normalize_song_key(title, artist)
    if song_key:
        return song_key

    source = track.get("source", "youtube")
    track_id = track.get("id") or track.get("trackId") or track.get("videoId")
    if track_id:
        return f"{source}:{track_id}"

    return None
