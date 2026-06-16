"""PlaylistLibrary: owns the saved-playlists dict and its on-disk persistence.

Extracted from the UI controller (the service-object step). It holds the in-memory
playlists dict and handles atomic load/save/delete + migration. Per-entry
normalization, serialization, and ordering are delegated back to the controller via
injected callables, because those need network/UI access the controller owns.
"""
import json
from pathlib import Path

import playlist_store


class PlaylistLibrary:
    def __init__(self, playlists_file, normalize_entry, serialize_entry, sort_key):
        self.playlists_file = Path(playlists_file)
        self.playlists = {}
        self._normalize_entry = normalize_entry
        self._serialize_entry = serialize_entry
        self._sort_key = sort_key

    def _backup_file(self):
        return self.playlists_file.with_name(f"{self.playlists_file.name}.backup")

    def _temp_file(self):
        return self.playlists_file.with_name(f"{self.playlists_file.name}.tmp")

    def sorted_items(self):
        return sorted(self.playlists.items(), key=self._sort_key)

    @staticmethod
    def _is_current_format(pl_data):
        return (
            isinstance(pl_data, dict)
            and "source" in pl_data
            and "id" in pl_data
            and "tracks" in pl_data
            and isinstance(pl_data.get("videos"), list)
        )

    def load(self):
        """Load playlists from disk into self.playlists. Returns True if the data was in a
        legacy format / under legacy keys and should be re-saved (migration)."""
        try:
            if not self.playlists_file.exists():
                print("No saved playlists file found, starting fresh")
                self.playlists = {}
                return False

            with self.playlists_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                print("Invalid playlist data format, starting fresh")
                self.playlists = {}
                return False

            self.playlists = {}
            migrated = False
            for stored_key, pl_data in data.items():
                entry = self._normalize_entry(stored_key, pl_data)
                if not entry:
                    migrated = True
                    continue

                store_key = playlist_store.playlist_storage_key(entry["source"], entry["id"])
                self.playlists[store_key] = entry
                if store_key != stored_key or not self._is_current_format(pl_data):
                    migrated = True

            print(f"Loaded {len(self.playlists)} playlists from {self.playlists_file}")
            return migrated
        except json.JSONDecodeError as e:
            print(f"Corrupted playlist file: {e}, starting fresh")
            self.playlists = {}
            if self.playlists_file.exists():
                backup_file = self._backup_file()
                self.playlists_file.replace(backup_file)
                print(f"Backed up corrupted file to {backup_file}")
            return False
        except Exception as e:
            print(f"Error loading playlists: {e}")
            self.playlists = {}
            return False

    def save(self):
        """Serialize and atomically write self.playlists. Raises on failure (after attempting
        to restore the backup) so the caller can surface the error to the user."""
        try:
            json_data = {}
            for playlist_key, pl_data in self.sorted_items():
                source, playlist_id = playlist_store.normalize_playlist_identity(playlist_key, pl_data)
                store_key = playlist_store.playlist_storage_key(source, playlist_id)
                json_data[store_key] = self._serialize_entry(playlist_key, pl_data)

            temp_file = self._temp_file()
            with temp_file.open("w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            if self.playlists_file.exists():
                self.playlists_file.replace(self._backup_file())

            temp_file.replace(self.playlists_file)
            print(f"Saved {len(self.playlists)} playlists to {self.playlists_file}")
        except Exception:
            backup_file = self._backup_file()
            if backup_file.exists():
                backup_file.replace(self.playlists_file)
                print("Restored backup file")
            raise

    def delete(self, playlist_keys):
        """Remove the given keys from the in-memory dict. Returns the number removed.
        Persisting is the caller's responsibility (so it can also refresh the UI)."""
        removed = 0
        for key in playlist_keys:
            if key in self.playlists:
                del self.playlists[key]
                removed += 1
        return removed
