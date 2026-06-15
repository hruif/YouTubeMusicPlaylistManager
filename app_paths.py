import os
import sys
from pathlib import Path

from app_info import APP_NAME


def running_from_bundle():
    return bool(getattr(sys, "frozen", False))


def resource_path(*parts):
    if running_from_bundle() and hasattr(sys, "_MEIPASS"):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent
    return base_path.joinpath(*parts)


def user_data_dir():
    if not running_from_bundle():
        return Path(__file__).resolve().parent

    return private_user_data_dir()


def private_user_data_dir():
    if sys.platform == "darwin":
        data_dir = Path.home() / "Library" / "Application Support" / APP_NAME
    elif os.name == "nt":
        app_data = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        data_dir = Path(app_data) / APP_NAME
    else:
        data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def user_data_path(filename):
    return user_data_dir() / filename


def private_user_data_path(filename):
    return private_user_data_dir() / filename
