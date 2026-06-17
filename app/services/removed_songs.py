"""RemovedSongsStore: remember songs that disappear from a playlist on Update.

Your local cache is effectively a snapshot until you Update; Update then replaces it
with the fresh fetch and would silently drop any song that YouTube/Spotify removed.
This archive captures the title + artist (no link — it's dead) of those songs so you
can still find them later. Local-only, persisted to ``removed_songs.json``.

`diff_removed_tracks` is the pure detector; the controller calls it during the update
loop (only when the new fetch is non-empty, so a failed/empty fetch can't wipe the
archive) and hands the result to `RemovedSongsStore.record`.
"""
import json
import os
import time
from pathlib import Path

from app.app_paths import user_data_path


def track_identity(track):
    if not isinstance(track, dict):
        return None
    return track.get("videoId") or track.get("id") or track.get("trackId")


def diff_removed_tracks(old_tracks, new_tracks):
    """Tracks present in ``old_tracks`` but absent from ``new_tracks`` (matched by id)."""
    new_ids = {track_identity(track) for track in new_tracks or [] if track_identity(track)}
    removed = []
    for track in old_tracks or []:
        identity = track_identity(track)
        if identity and identity not in new_ids:
            removed.append(track)
    return removed


class RemovedSongsStore:
    def __init__(self, store_file=None):
        self.store_file = Path(store_file or user_data_path("removed_songs.json"))
        self._data = self._load()

    def _load(self):
        try:
            with self.store_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def record(self, playlist_key, playlist_name, tracks, removed_at=None):
        """Archive removed ``tracks`` for a playlist, deduped by song id (earliest
        sighting kept). Returns the count of newly-archived songs."""
        if not tracks:
            return 0
        removed_at = int(removed_at if removed_at is not None else time.time())

        entry = self._data.get(playlist_key)
        if not isinstance(entry, dict):
            entry = {"name": playlist_name, "songs": []}
        entry["name"] = playlist_name or entry.get("name") or "Unknown Playlist"
        songs = entry.setdefault("songs", [])

        existing_ids = {song.get("id") for song in songs if isinstance(song, dict)}
        added = 0
        for track in tracks:
            identity = track_identity(track)
            if not identity or identity in existing_ids:
                continue
            songs.append({
                "id": identity,
                "title": track.get("title") or "Unknown Title",
                "artist": track.get("artist") or "Unknown Artist",
                "source": track.get("source", "youtube"),
                "removed_at": removed_at,
            })
            existing_ids.add(identity)
            added += 1

        if added:
            self._data[playlist_key] = entry
            self._save()
        return added

    def for_playlist(self, playlist_key):
        entry = self._data.get(playlist_key)
        if not isinstance(entry, dict):
            return []
        songs = entry.get("songs")
        return list(songs) if isinstance(songs, list) else []

    def clear(self, playlist_key):
        if playlist_key in self._data:
            del self._data[playlist_key]
            self._save()

    def _save(self):
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.store_file.with_suffix(self.store_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(self._data, file, indent=2)
        os.replace(tmp_path, self.store_file)
