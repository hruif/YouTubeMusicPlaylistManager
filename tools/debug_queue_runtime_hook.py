"""PyInstaller runtime hook for debug builds.

Included in the bundle only when the app is built with
`python tools/build_macos_app.py --debug` (which sets PLAYLIST_MANAGER_BUILD_DEBUG).
It turns on the otherwise-hidden experimental YouTube queue actions (including the
"Play in YouTube Music" button) by defaulting the env var the UI checks, so the
feature is visible without the user setting anything. A real environment variable
still overrides this, and release builds never include this hook.

It also marks this as the debug bundle so it uses a separate user-data folder and
single-instance lock ("… (Debug)"), letting it run alongside the release build
without sharing playlists, headers, temp-playlist records, or the lock.
"""
import os

os.environ.setdefault("PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS", "1")
os.environ.setdefault("PLAYLIST_MANAGER_DEBUG_BUILD", "1")
