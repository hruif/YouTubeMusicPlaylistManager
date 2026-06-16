"""CustomNamesStore: per-song user aliases for easier searching.

Local-only metadata — never written to any account. Keyed by the song's
normalized title+artist key (the same key the combined view groups on), so an
alias follows the song across every playlist it appears in. Persisted atomically
to ``custom_song_names.json`` in the user data dir (next to ``saved_playlists``).
"""
import json
import os
from pathlib import Path

from app.app_paths import user_data_path
from app.services import playlist_store


def song_key(track):
    """Stable per-song key for aliasing. Prefers the normalized title+artist key
    (matches combined-view grouping); falls back to ``source:id``. None if neither
    is available."""
    if not isinstance(track, dict):
        return None
    key = playlist_store.combined_track_key(track)
    if key:
        return key
    track_id = track.get("videoId") or track.get("id") or track.get("trackId")
    if not track_id:
        return None
    return f"{track.get('source', 'youtube')}:{track_id}"


class CustomNamesStore:
    def __init__(self, store_file=None):
        self.store_file = Path(store_file or user_data_path("custom_song_names.json"))
        self._names = self._load()

    def _load(self):
        try:
            with self.store_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in data.items()
            if isinstance(value, str) and value.strip()
        }

    def get(self, track):
        key = song_key(track)
        return self._names.get(key, "") if key else ""

    def set(self, track, name):
        """Set or clear (empty name removes) a song's alias. Returns True if the
        stored value changed."""
        key = song_key(track)
        if not key:
            return False
        name = str(name or "").strip()
        if name:
            if self._names.get(key) == name:
                return False
            self._names[key] = name
        else:
            if key not in self._names:
                return False
            del self._names[key]
        self._save()
        return True

    def _save(self):
        self.store_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.store_file.with_suffix(self.store_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(self._names, file, indent=2)
        os.replace(tmp_path, self.store_file)
