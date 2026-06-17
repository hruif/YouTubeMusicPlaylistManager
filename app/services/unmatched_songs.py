"""UnmatchedSongsStore: per-playlist list of Spotify songs that couldn't be confidently
matched during a Spotify -> YouTube transfer.

Persisted (to ``unmatched_songs.json``) so the list survives restarts and the user can find
and add the songs manually later — surfaced in the converted playlist's Details window, where
each entry gets a "Search on YouTube Music" link. Keyed by the new YouTube playlist's storage
key.
"""
import json
import os
from pathlib import Path

from app.app_paths import user_data_path


class UnmatchedSongsStore:
    def __init__(self, store_file=None):
        self.store_file = Path(store_file or user_data_path("unmatched_songs.json"))
        self._data = self._load()

    def _load(self):
        try:
            with self.store_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def set(self, playlist_key, songs):
        """Replace the unmatched list for a playlist with ``[{title, artist}, ...]`` (deduped
        by title+artist; entries without a title are dropped). An empty list clears it."""
        cleaned = []
        seen = set()
        for song in songs or []:
            if not isinstance(song, dict):
                continue
            title = str(song.get("title") or "").strip()
            artist = str(song.get("artist") or "").strip()
            if not title:
                continue
            dedup_key = (title.lower(), artist.lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            cleaned.append({"title": title, "artist": artist})

        if cleaned:
            self._data[playlist_key] = cleaned
        elif playlist_key in self._data:
            del self._data[playlist_key]
        self._save()

    def for_playlist(self, playlist_key):
        songs = self._data.get(playlist_key)
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
