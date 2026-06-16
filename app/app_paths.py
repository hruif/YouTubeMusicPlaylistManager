import os
import sys
from pathlib import Path

from app.app_info import APP_NAME

# This module lives at app/app_paths.py, so the repo root (which holds assets/ and, when running
# from source, the user's data files) is two levels up from this file.
_REPO_ROOT = Path(__file__).resolve().parent.parent


def running_from_bundle():
    return bool(getattr(sys, "frozen", False))


def resource_path(*parts):
    if running_from_bundle() and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = _REPO_ROOT
    return base_path.joinpath(*parts)


def user_data_dir():
    if not running_from_bundle():
        return _REPO_ROOT

    return private_user_data_dir()


def _is_debug_build():
    return os.environ.get("PLAYLIST_MANAGER_DEBUG_BUILD", "").lower() in {"1", "true", "yes", "on"}


def _data_dir_app_name():
    # The debug *bundle* isolates its data + single-instance lock (own "(Debug)" folder) so it can
    # run alongside the release build instead of sharing playlists, headers, and the lock. Only the
    # bundled debug build sets PLAYLIST_MANAGER_DEBUG_BUILD; from-source runs are unaffected.
    if running_from_bundle() and _is_debug_build():
        return f"{APP_NAME} (Debug)"
    return APP_NAME


def private_user_data_dir():
    app_name = _data_dir_app_name()
    if sys.platform == "darwin":
        data_dir = Path.home() / "Library" / "Application Support" / app_name
    elif os.name == "nt":
        app_data = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        data_dir = Path(app_data) / app_name
    else:
        data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / app_name

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def user_data_path(filename):
    return user_data_dir() / filename


def private_user_data_path(filename):
    return private_user_data_dir() / filename
