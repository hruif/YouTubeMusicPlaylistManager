"""Small persistent key/value store for application preferences.

Settings live in ``app_settings.json`` inside the user data directory (next to
the code when running from source, or the OS application-support folder in the
packaged app). Writes are atomic so a crash mid-write cannot corrupt the file.
"""

import json
import os
from pathlib import Path

from app_paths import user_data_path

AUTO_DELETE_TEMP_ON_EXIT = "auto_delete_temp_on_exit"
USE_DISPLAY_WINDOWS = "use_display_windows"


class AppSettings:
    def __init__(self, settings_file=None):
        self.settings_file = Path(settings_file or user_data_path("app_settings.json"))
        self._data = self._load()

    def _load(self):
        try:
            with self.settings_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def get_bool(self, key, default=False):
        value = self._data.get(key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def set(self, key, value):
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self._save()

    def _save(self):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.settings_file.with_suffix(self.settings_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(self._data, file, indent=2)
        os.replace(tmp_path, self.settings_file)
