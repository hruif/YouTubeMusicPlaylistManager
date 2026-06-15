import contextlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import ttk, messagebox
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.exceptions import BadOAuthClient

from app_info import APP_NAME, APP_VERSION
from app_paths import resource_path, user_data_path
from playlist_url_window import PlaylistURLWindow
from update_checker import UpdateChecker
from youtube_data_api import YouTubeDataApiClient
from youtube_music_account import YouTubeMusicAccount
from youtube_player import YouTubeQueuePlayer

try:
    from spotapi import PublicPlaylist
    SPOTAPI_AVAILABLE = True
except ImportError:
    PublicPlaylist = None
    SPOTAPI_AVAILABLE = False


class PlaylistManagerUI:
    """Main Tk shell that coordinates playlist data, displays, and playback actions."""

    PLAYLIST_FILE = user_data_path("saved_playlists.json")
    ASSETS_DIR = resource_path("assets")
    WEB_DIR = resource_path("web")
    YOUTUBE_PLAYER_FILE = WEB_DIR / "youtube_queue_player.html"
    YOUTUBE_PLAYER_LAUNCHER = resource_path("youtube_player_window.py")
    YOUTUBE_PLAYER_HOST = "127.0.0.1"
    YOUTUBE_QUEUE_CACHE_LIMIT = 20
    YOUTUBE_QUEUE_ACTIONS_ENV_VAR = "PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS"
    DISABLE_UPDATE_CHECK_ENV_VAR = "PLAYLIST_MANAGER_DISABLE_UPDATE_CHECK"
    PLAYLIST_DISPLAY_LIMIT = 140
    YOUTUBE_TEMP_PLAYLIST_CHUNK_SIZE = 50
    SOURCE_LABELS = {
        'youtube': 'YouTube',
        'spotify': 'Spotify'
    }
    YOUTUBE_MUSIC_ONLY_TYPES = {
        'MUSIC_VIDEO_TYPE_ATV'
    }
    YOUTUBE_QUEUE_PLAYABLE_STATUSES = {
        "Queue OK",
        "Unknown"
    }
    COMBINED_SORT_OPTIONS = {
        'Title (A-Z)': 'title',
        'Artist (A-Z)': 'artist',
        'Playlist Name': 'playlist',
        'Source': 'source',
        'Original Playlist Order': 'original'
    }

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1180x720")
        self.root.minsize(1020, 640)
        
        # Initialize YTMusic (no authentication needed for public playlists)
        try:
            self.ytmusic = YTMusic()
            print("YTMusic initialized for public playlist access")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize YTMusic: {e}")
            self.ytmusic = None

        # Initialize SpotAPI support (for Spotify-like imports)
        self.spotapi_available = SPOTAPI_AVAILABLE
        
        # Store saved playlists
        self.saved_playlists = {}  # {source:playlist_id: {source, id, name, videos, tracks}}
        self.playlists_file = self.PLAYLIST_FILE
        
        # Load saved playlists on startup
        self.load_playlists()
        
        # Show loaded playlists count
        if self.saved_playlists:
            print(f"Loaded {len(self.saved_playlists)} saved playlists")
            # Could add a status label here if desired

        self.use_display_windows_var = tk.BooleanVar(value=False)
        self.app_icon_image = self._load_app_icon_image()
        self.source_logo_images = self._build_source_logo_images()
        self.sidebar_playlist_vars = []
        self.display_playlist_vars = []
        self.active_find_entry = None
        self.current_display_view = 'empty'
        self.update_checker = UpdateChecker()
        self.youtube_account = YouTubeMusicAccount(opener=self._open_external_url)
        self.authenticated_ytmusic = self._build_authenticated_ytmusic()
        self.youtube_player = self._build_youtube_player()
        self._configure_window_icon(self.root)
        self.style = ttk.Style()
        self._configure_button_feedback()
        self.style.configure("SourceLogo.Treeview", rowheight=32)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.main_frame = ttk.Frame(root, padding="14")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.sidebar_frame = ttk.Frame(self.main_frame, width=270)
        self.sidebar_frame.grid(row=0, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 14))
        self.sidebar_frame.grid_propagate(False)

        self.display_frame = ttk.Frame(self.main_frame)
        self.display_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        title = ttk.Label(self.sidebar_frame, text="Playlist Manager", font=("Helvetica", 15, "bold"))
        title.grid(row=0, column=0, sticky=tk.W, pady=(0, 14))

        search_label = ttk.Label(self.sidebar_frame, text="Search songs:")
        search_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))

        self.search_entry = ttk.Entry(self.sidebar_frame)
        self.search_entry.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        self.root.bind_all("<Control-f>", self._focus_active_find_or_sidebar)
        self.root.bind_all("<Command-f>", self._focus_active_find_or_sidebar)

        button_frame = ttk.Frame(self.sidebar_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        button_frame.columnconfigure(0, weight=1)

        search_button = ttk.Button(button_frame, text="Search", command=self.on_search)
        search_button.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)

        add_playlist_button = ttk.Button(button_frame, text="Add Playlist URL", command=self.open_playlist_window)
        add_playlist_button.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)

        view_playlists_button = ttk.Button(button_frame, text="View Saved Playlists", command=self.view_saved_playlists)
        view_playlists_button.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)

        find_duplicates_button = ttk.Button(button_frame, text="Find Duplicates in Selection", command=self.find_duplicate_songs)
        find_duplicates_button.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=2)

        update_selected_button = ttk.Button(button_frame, text="Update Selected Playlists", command=self.update_selected_playlists)
        update_selected_button.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=2)

        combined_songs_button = ttk.Button(button_frame, text="View Combined Songs", command=self.open_combined_songs_selector)
        combined_songs_button.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=2)

        # "Play in YouTube Music" creates a private temporary playlist via OAuth, but most
        # YouTube Music tracks will not actually play through the resulting queue (no official
        # streaming API). It is hidden alongside the other experimental queue actions and only
        # appears when PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS is set, for debugging.
        if self._show_youtube_queue_actions():
            play_youtube_music_button = ttk.Button(button_frame, text="Play in YouTube Music", command=self.play_selection_in_youtube_music)
            play_youtube_music_button.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=2)

        settings_button = ttk.Button(button_frame, text="Settings", command=self.show_settings_display)
        settings_button.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(12, 2))

        self.playlist_selector_container = ttk.LabelFrame(self.sidebar_frame, text="Playlists", padding=(6, 4))
        self.playlist_selector_container.grid(row=5, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.sidebar_selection_actions = ttk.Frame(self.sidebar_frame)
        self.sidebar_selection_actions.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(8, 0))
        self.sidebar_selection_actions.columnconfigure(0, weight=1)
        self.sidebar_selection_actions.columnconfigure(1, weight=1)

        select_all_button = ttk.Button(self.sidebar_selection_actions, text="Select All", command=lambda: self._set_playlist_selection(self._active_playlist_vars(), True))
        select_all_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 4))

        clear_button = ttk.Button(self.sidebar_selection_actions, text="Clear", command=lambda: self._set_playlist_selection(self._active_playlist_vars(), False))
        clear_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(4, 0))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.sidebar_frame.columnconfigure(0, weight=1)
        self.sidebar_frame.rowconfigure(5, weight=1)
        self.display_frame.columnconfigure(0, weight=1)
        self.display_frame.rowconfigure(1, weight=1)
        self.refresh_sidebar_playlists()
        self.show_empty_display()
        self._schedule_initial_update_check()
        self._schedule_temporary_playlist_cleanup_prompt()

    def _on_close(self):
        self.youtube_player.shutdown()
        self.root.destroy()

    def _load_app_icon_image(self):
        icon_path = self.ASSETS_DIR / "app_icon.png"
        if not icon_path.exists():
            return None
        try:
            return tk.PhotoImage(file=str(icon_path))
        except tk.TclError:
            return None

    def _configure_window_icon(self, window):
        if getattr(self, 'app_icon_image', None) is None:
            return
        try:
            window.iconphoto(True, self.app_icon_image)
        except tk.TclError:
            pass

    def _configure_button_feedback(self):
        try:
            self.style.configure("TButton", padding=(7, 4))
            self.style.map(
                "TButton",
                background=[
                    ("pressed", "#cfe3ff"),
                    ("active", "#eaf2ff"),
                ],
                foreground=[
                    ("disabled", "#8a8a8a"),
                    ("pressed", "#0b4f9c"),
                    ("active", "#0b4f9c"),
                ],
                relief=[
                    ("pressed", "sunken"),
                    ("!pressed", "raised"),
                ],
            )
        except tk.TclError:
            pass

        self.root.bind_class("TButton", "<Enter>", self._button_feedback_enter, add="+")
        self.root.bind_class("TButton", "<Leave>", self._button_feedback_leave, add="+")
        self.root.bind_class("TButton", "<ButtonPress-1>", self._button_feedback_press, add="+")
        self.root.bind_class("TButton", "<ButtonRelease-1>", self._button_feedback_release, add="+")

    def _button_feedback_enter(self, event):
        widget = event.widget
        if not hasattr(widget, "state") or widget.instate(["disabled"]):
            return
        widget.state(["active"])
        with contextlib.suppress(tk.TclError):
            widget.configure(cursor="pointinghand" if sys.platform == "darwin" else "hand2")

    def _button_feedback_leave(self, event):
        self._reset_button_feedback(event.widget)

    def _button_feedback_press(self, event):
        widget = event.widget
        if not hasattr(widget, "state") or widget.instate(["disabled"]):
            return
        widget.state(["pressed"])
        with contextlib.suppress(tk.TclError):
            widget.update_idletasks()

    def _button_feedback_release(self, event):
        widget = event.widget
        if not hasattr(widget, "state"):
            return
        self.root.after(140, lambda: self._reset_button_feedback(widget))

    def _reset_button_feedback(self, widget):
        if not hasattr(widget, "state"):
            return
        with contextlib.suppress(tk.TclError):
            widget.state(["!pressed", "!active"])
            widget.configure(cursor="")

    def _open_external_url(self, url):
        url = str(url or "").strip()
        if not url:
            return False

        try:
            if webbrowser.open_new_tab(url):
                return True
        except Exception:
            pass

        if sys.platform == "darwin":
            try:
                subprocess.Popen(["open", url])
                return True
            except Exception:
                pass

        return False

    def _build_youtube_player(self):
        return YouTubeQueuePlayer(
            player_file=self.YOUTUBE_PLAYER_FILE,
            launcher_file=self.YOUTUBE_PLAYER_LAUNCHER,
            host=self.YOUTUBE_PLAYER_HOST,
            queue_cache_limit=self.YOUTUBE_QUEUE_CACHE_LIMIT,
            unavailable_callback=self._mark_youtube_track_unavailable
        )

    def _build_authenticated_ytmusic(self):
        if not self.youtube_account.is_ready():
            return None

        try:
            return self.youtube_account.build_authenticated_client()
        except Exception as e:
            print(f"Could not initialize authenticated YouTube Music client: {e}")
            return None

    def _youtube_music_client(self):
        if self.authenticated_ytmusic is None:
            self.authenticated_ytmusic = self._build_authenticated_ytmusic()
        return self.authenticated_ytmusic

    def _youtube_data_api_client(self):
        return YouTubeDataApiClient(
            client_file=self.youtube_account.client_file,
            token_file=self.youtube_account.token_file,
        )

    def _is_youtube_music_connected(self):
        return self.authenticated_ytmusic is not None or self.youtube_account.is_ready()

    def _youtube_music_auth_status(self):
        if self._is_youtube_music_connected():
            return "Connected"
        if self.youtube_account.token_file.exists():
            return "Saved token incomplete, reconnect needed"
        if self.youtube_account.has_client_credentials():
            return "OAuth client saved, sign-in needed"
        return "Not connected"

    def _mark_youtube_track_unavailable(self, payload):
        payload = dict(payload or {})
        root = getattr(self, 'root', None)
        if root is not None:
            try:
                root.after(0, lambda: self._apply_youtube_track_unavailable(payload))
                return
            except (RuntimeError, tk.TclError):
                pass

        self._apply_youtube_track_unavailable(payload)

    def _apply_youtube_track_unavailable(self, payload):
        video_id = str(payload.get('videoId') or '').strip()
        if not video_id:
            return

        error_code = payload.get('errorCode')
        unavailable_reason = f"iframe error {error_code}" if error_code is not None else "iframe unavailable"
        changed = False
        for pl_data in self.saved_playlists.values():
            if pl_data.get('source') != 'youtube':
                continue

            for track in pl_data.get('tracks', []):
                if not isinstance(track, dict):
                    continue
                if self._track_youtube_video_id('youtube', track) != video_id:
                    continue

                if (
                    track.get('queuePlayable') is False
                    and track.get('queueStatus') == "Unavailable"
                    and track.get('queueUnavailableReason') == unavailable_reason
                ):
                    continue

                track['queuePlayable'] = False
                track['queueStatus'] = "Unavailable"
                track['queueUnavailableReason'] = unavailable_reason
                changed = True

        if changed:
            self.save_playlists()
            self._refresh_live_combined_if_active()

    def _schedule_initial_update_check(self):
        if os.environ.get(self.DISABLE_UPDATE_CHECK_ENV_VAR, "").lower() in {"1", "true", "yes", "on"}:
            return
        self.root.after(1500, lambda: self.check_for_updates(silent=True))

    def _schedule_temporary_playlist_cleanup_prompt(self):
        if not self._is_youtube_music_connected():
            return
        if not self.youtube_account.load_temporary_playlists():
            return
        self.root.after(3500, self._prompt_for_temporary_playlist_cleanup)

    def _prompt_for_temporary_playlist_cleanup(self):
        records = self.youtube_account.load_temporary_playlists()
        if not records:
            return

        should_delete = messagebox.askyesno(
            "Temporary YouTube Music Playlists",
            (
                f"{len(records)} temporary playlist"
                f"{'' if len(records) == 1 else 's'} from a previous queue session are still saved.\n\n"
                "Delete them now?"
            )
        )
        if should_delete:
            self.delete_temporary_youtube_playlists(prompt=False)

    def check_for_updates(self, silent=False):
        def worker():
            try:
                update_info = self.update_checker.check()
            except Exception as error:
                if not silent:
                    self.root.after(0, lambda error=error: messagebox.showerror("Update Check Failed", str(error)))
                return

            self.root.after(0, lambda: self._handle_update_result(update_info, silent))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_update_result(self, update_info, silent):
        if update_info is None:
            if not silent:
                messagebox.showinfo("No Update Available", f"{APP_NAME} {APP_VERSION} is up to date.")
            return

        should_open = messagebox.askyesno(
            "Update Available",
            (
                f"{update_info.title} is available.\n\n"
                f"Installed version: {APP_VERSION}\n"
                f"Latest version: {update_info.version}\n\n"
                "Open the download page?"
            )
        )
        if should_open:
            self._open_external_url(update_info.url)
    
    def load_playlists(self):
        """Load saved playlists from file"""
        try:
            if not self.playlists_file.exists():
                print("No saved playlists file found, starting fresh")
                self.saved_playlists = {}
                return

            with self.playlists_file.open('r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                print("Invalid playlist data format, starting fresh")
                self.saved_playlists = {}
                return

            self.saved_playlists = {}
            migrated = False
            for stored_key, pl_data in data.items():
                entry = self._normalize_playlist_entry(stored_key, pl_data)
                if not entry:
                    migrated = True
                    continue

                store_key = self._playlist_storage_key(entry['source'], entry['id'])
                self.saved_playlists[store_key] = entry
                if store_key != stored_key or not self._is_current_playlist_format(pl_data):
                    migrated = True

            print(f"Loaded {len(self.saved_playlists)} playlists from {self.playlists_file}")

            if migrated:
                print("Migrating playlist data to the current format...")
                self.save_playlists()
                print("Migration complete.")
        except json.JSONDecodeError as e:
            print(f"Corrupted playlist file: {e}, starting fresh")
            self.saved_playlists = {}
            # Backup the corrupted file
            if self.playlists_file.exists():
                backup_file = self._playlists_backup_file()
                self.playlists_file.replace(backup_file)
                print(f"Backed up corrupted file to {backup_file}")
        except Exception as e:
            print(f"Error loading playlists: {e}")
            self.saved_playlists = {}

    # SpotAPI (spotapi.PublicPlaylist) is used for public Spotify playlist access.
    # No client credentials are required for public playlist fetching via SpotAPI.

    def _playlists_backup_file(self):
        return self.playlists_file.with_name(f"{self.playlists_file.name}.backup")

    def _playlists_temp_file(self):
        return self.playlists_file.with_name(f"{self.playlists_file.name}.tmp")

    def _playlist_storage_key(self, source, playlist_id):
        return f"{source}:{playlist_id}"

    def _split_storage_key(self, stored_key):
        if isinstance(stored_key, str) and ':' in stored_key:
            source, playlist_id = stored_key.split(':', 1)
            if source in self.SOURCE_LABELS and playlist_id:
                return source, playlist_id
        return 'youtube', stored_key

    def _normalize_playlist_identity(self, stored_key, pl_data):
        stored_source, stored_playlist_id = self._split_storage_key(stored_key)

        source = pl_data.get('source') or stored_source
        if source not in self.SOURCE_LABELS:
            source = stored_source

        playlist_id = pl_data.get('id') or stored_playlist_id
        if isinstance(playlist_id, str) and playlist_id.startswith(f"{source}:"):
            playlist_id = playlist_id.split(':', 1)[1]

        return source, playlist_id

    def _normalize_playlist_entry(self, stored_key, pl_data):
        if not isinstance(pl_data, dict):
            return None

        source, playlist_id = self._normalize_playlist_identity(stored_key, pl_data)
        if not playlist_id:
            return None

        tracks = self._normalize_tracks(source, pl_data.get('tracks', []))
        videos = self._coerce_id_set(pl_data.get('videos'))
        if not videos:
            videos = self._coerce_id_set(track.get('id') for track in tracks)

        if not tracks and videos and source == 'youtube':
            tracks = self._load_youtube_tracks_for_legacy_playlist(playlist_id, videos)

        return self._build_playlist_entry(
            source=source,
            playlist_id=playlist_id,
            playlist_name=pl_data.get('name', 'Unnamed Playlist'),
            item_ids=videos,
            tracks=tracks
        )

    def _is_current_playlist_format(self, pl_data):
        return (
            isinstance(pl_data, dict)
            and 'source' in pl_data
            and 'id' in pl_data
            and 'tracks' in pl_data
            and isinstance(pl_data.get('videos'), list)
        )

    def _coerce_id_set(self, values):
        if values is None:
            return set()
        if isinstance(values, set):
            return {value for value in values if value}
        if isinstance(values, (list, tuple)):
            return {value for value in values if value}
        if not isinstance(values, str):
            try:
                return {value for value in values if value}
            except TypeError:
                return set()
        return {values} if values else set()

    def _normalize_tracks(self, source, tracks):
        if not isinstance(tracks, list):
            return []

        normalized_tracks = []
        for track in tracks:
            if not isinstance(track, dict):
                continue

            normalized = dict(track)
            track_id = normalized.get('id') or normalized.get('trackId') or normalized.get('videoId')
            if not track_id:
                continue
            track_id = str(track_id)
            if source == 'spotify' and track_id.startswith('spotify:track:'):
                track_id = track_id.rsplit(':', 1)[1]

            normalized['id'] = track_id
            normalized['source'] = source
            if source == 'youtube':
                normalized['videoId'] = normalized.get('videoId') or track_id
            elif source == 'spotify':
                normalized['trackId'] = normalized.get('trackId') or track_id

            normalized.setdefault('title', 'Unknown Title')
            normalized.setdefault('artist', 'Unknown Artist')
            if source == 'youtube' and (
                'queueStatus' not in normalized or 'queuePlayable' not in normalized
            ):
                normalized.update(self._youtube_queue_marker(source, normalized))
            normalized_tracks.append(normalized)

        return normalized_tracks

    def _load_youtube_tracks_for_legacy_playlist(self, playlist_id, video_ids):
        if not self.ytmusic:
            return self._fallback_youtube_tracks(video_ids)

        try:
            playlist_data = self.ytmusic.get_playlist(playlist_id, limit=500)
            _, tracks = self._extract_track_metadata(playlist_data)
            return [track for track in tracks if track.get('videoId') in video_ids]
        except Exception as e:
            print(f"Could not fetch metadata for playlist {playlist_id}: {e}")
            return self._fallback_youtube_tracks(video_ids)

    def _fallback_youtube_tracks(self, video_ids):
        tracks = []
        for video_id in sorted(video_ids):
            track = {
                'id': video_id,
                'videoId': video_id,
                'title': f'Song ID: {video_id}',
                'artist': 'Unknown Artist',
                'source': 'youtube'
            }
            track.update(self._youtube_queue_marker('youtube', track))
            tracks.append(track)
        return tracks

    def _build_playlist_entry(self, source, playlist_id, playlist_name, item_ids, tracks):
        return {
            'source': source,
            'id': playlist_id,
            'name': playlist_name or 'Unnamed Playlist',
            'videos': set(item_ids),
            'tracks': tracks
        }

    def _serialize_playlist_entry(self, playlist_key, pl_data):
        source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
        return {
            'source': source,
            'id': playlist_id,
            'name': pl_data.get('name', 'Unnamed Playlist'),
            'videos': sorted(self._coerce_id_set(pl_data.get('videos'))),
            'tracks': self._normalize_tracks(source, pl_data.get('tracks', []))
        }

    def save_playlists(self):
        """Save playlists to file"""
        try:
            json_data = {}
            for playlist_key, pl_data in self._sorted_playlist_items():
                source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
                store_key = self._playlist_storage_key(source, playlist_id)
                json_data[store_key] = self._serialize_playlist_entry(playlist_key, pl_data)

            temp_file = self._playlists_temp_file()
            with temp_file.open('w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            if self.playlists_file.exists():
                self.playlists_file.replace(self._playlists_backup_file())

            temp_file.replace(self.playlists_file)
            print(f"Saved {len(self.saved_playlists)} playlists to {self.playlists_file}")
        except Exception as e:
            print(f"Error saving playlists: {e}")
            messagebox.showerror("Error", f"Failed to save playlists: {e}")
            # Try to restore backup
            backup_file = self._playlists_backup_file()
            if backup_file.exists():
                backup_file.replace(self.playlists_file)
                print("Restored backup file")
    
    def _extract_playlist_name(self, playlist, fallback_name='Unnamed Playlist'):
        playlist_name = self._extract_text_value(playlist.get('title'))
        if playlist_name:
            return playlist_name

        header = playlist.get('header')
        playlist_name = None
        if isinstance(header, dict):
            playlist_name = self._extract_text_value(header.get('title'))
        if playlist_name:
            return playlist_name

        if isinstance(header, dict):
            renderer = (
                header.get('musicDetailHeaderRenderer')
                or header.get('musicResponsiveHeaderRenderer')
            )
            if isinstance(renderer, dict):
                playlist_name = self._extract_text_value(renderer.get('title'))
                if playlist_name:
                    return playlist_name

        return fallback_name

    def _extract_text_value(self, value):
        if isinstance(value, str):
            return value
        if not isinstance(value, dict):
            return None

        if isinstance(value.get('text'), str):
            return value['text']

        runs = value.get('runs')
        if isinstance(runs, list) and runs:
            first_run = runs[0]
            if isinstance(first_run, dict) and isinstance(first_run.get('text'), str):
                return first_run['text']

        return None

    def _extract_track_metadata(self, playlist):
        tracks_data = []
        video_ids = set()

        for track in playlist.get('tracks', []):
            if 'videoId' not in track:
                continue

            video_id = track['videoId']
            video_ids.add(video_id)

            title = track.get('title', 'Unknown Title')
            artist = self._extract_youtube_artist(track.get('artists', []))
            thumbnails = track.get('thumbnails') if isinstance(track.get('thumbnails'), list) else []

            metadata = {
                'id': video_id,
                'videoId': video_id,
                'title': title,
                'artist': artist,
                'source': 'youtube',
                'videoType': track.get('videoType'),
                'isAvailable': track.get('isAvailable'),
                'thumbnails': thumbnails,
                'thumbnailUrl': self._best_thumbnail_url(thumbnails)
            }
            metadata.update(self._youtube_queue_marker('youtube', metadata))
            tracks_data.append(metadata)

        return video_ids, tracks_data

    def _extract_youtube_artist(self, artists):
        if isinstance(artists, list) and artists:
            first_artist = artists[0]
            if isinstance(first_artist, dict):
                return first_artist.get('name') or 'Unknown Artist'
            return str(first_artist)
        return 'Unknown Artist'

    def _best_thumbnail_url(self, thumbnails):
        if not thumbnails:
            return None

        valid_thumbnails = [
            thumbnail
            for thumbnail in thumbnails
            if isinstance(thumbnail, dict) and thumbnail.get('url')
        ]
        if not valid_thumbnails:
            return None

        best_thumbnail = max(
            valid_thumbnails,
            key=lambda thumbnail: (thumbnail.get('width') or 0) * (thumbnail.get('height') or 0)
        )
        return best_thumbnail.get('url')

    def _get_spotify_playlist_name(self, info, fallback_name):
        if not info:
            return fallback_name

        if isinstance(info, dict):
            if info.get('name'):
                return info['name']

            data = info.get('data')
            if isinstance(data, dict):
                playlist_v2 = data.get('playlistV2')
                if isinstance(playlist_v2, dict):
                    if playlist_v2.get('name'):
                        return playlist_v2.get('name')
                    content = playlist_v2.get('content')
                    if isinstance(content, dict) and content.get('name'):
                        return content.get('name')
                if data.get('name'):
                    return data.get('name')
            return fallback_name

        try:
            for inf in info:
                if isinstance(inf, dict):
                    return self._get_spotify_playlist_name(inf, fallback_name)
        except Exception:
            pass

        return fallback_name

    def _extract_spotify_track_from_item(self, item):
        if not isinstance(item, dict):
            return None

        track = None
        if 'track' in item and isinstance(item['track'], dict):
            track = item['track']
        elif 'item' in item and isinstance(item['item'], dict):
            track = item['item'].get('data') or item['item']
        elif 'itemV2' in item and isinstance(item['itemV2'], dict):
            track = item['itemV2'].get('data') or item['itemV2']
        elif 'data' in item and isinstance(item['data'], dict):
            track = item['data']
        else:
            track = item

        if not track or not isinstance(track, dict):
            return None

        track_id = track.get('id') or track.get('trackId') or track.get('uri')
        if not track_id:
            nested = track.get('track') if isinstance(track.get('track'), dict) else None
            if nested:
                track_id = nested.get('id') or nested.get('uri')
                track = nested
        if not track_id:
            return None
        track_id = str(track_id)
        if track_id.startswith('spotify:track:'):
            track_id = track_id.rsplit(':', 1)[1]

        title = track.get('name') or track.get('title') or ''
        artist = self._extract_spotify_artist_name(track.get('artists'))

        return {
            'id': track_id,
            'trackId': track_id,
            'title': title,
            'artist': artist,
            'source': 'spotify'
        }

    def _extract_spotify_artist_name(self, artists):
        if isinstance(artists, list) and artists:
            return self._spotify_artist_name_from_value(artists[0])

        if isinstance(artists, dict):
            artist_items = artists.get('items')
            if isinstance(artist_items, list) and artist_items:
                return self._spotify_artist_name_from_value(artist_items[0])

        return ''

    def _spotify_artist_name_from_value(self, artist):
        if isinstance(artist, dict):
            profile = artist.get('profile')
            profile_name = profile.get('name') if isinstance(profile, dict) else None
            return artist.get('name') or profile_name or ''
        return str(artist) if artist else ''

    def _extract_spotify_items_from_page(self, page):
        if isinstance(page, list):
            return page
        if not isinstance(page, dict):
            return []

        for key in ('items', 'tracks', 'data', 'content', 'contents', 'playlistV2'):
            value = page.get(key)
            if isinstance(value, list):
                return value
            nested_items = self._extract_spotify_items_from_page(value)
            if nested_items:
                return nested_items

        if any(key in page for key in ('track', 'item', 'itemV2', 'id', 'trackId', 'uri')):
            return [page]

        return []

    def _fetch_youtube_playlist_entry(self, playlist_id, fallback_name='Unnamed Playlist'):
        if not self.ytmusic:
            raise RuntimeError("YTMusic is not initialized")

        playlist = self.ytmusic.get_playlist(playlist_id, limit=500)
        playlist_name = self._extract_playlist_name(playlist, fallback_name)
        video_ids, tracks_data = self._extract_track_metadata(playlist)
        return self._build_playlist_entry('youtube', playlist_id, playlist_name, video_ids, tracks_data)

    def _fetch_spotify_playlist_entry(self, playlist_id, fallback_name=None):
        if not self.spotapi_available or PublicPlaylist is None:
            raise RuntimeError("SpotAPI (spotapi) is not available")

        track_ids = set()
        tracks_data = []
        playlist_name = fallback_name or f"Spotify Playlist {playlist_id}"

        pl = PublicPlaylist(playlist_id)
        try:
            info = pl.get_playlist_info()
            playlist_name = self._get_spotify_playlist_name(info, playlist_name)
        except Exception as e:
            print(f"Could not fetch Spotify playlist info for {playlist_id}: {e}")

        for page in pl.paginate_playlist():
            for item in self._extract_spotify_items_from_page(page):
                track = self._extract_spotify_track_from_item(item)
                if not track:
                    continue
                track_ids.add(track['id'])
                tracks_data.append(track)

        if not tracks_data:
            raise RuntimeError("No valid Spotify tracks were found.")

        return self._build_playlist_entry('spotify', playlist_id, playlist_name, track_ids, tracks_data)

    def _normalize_song_key(self, title, artist):
        combined = f"{title or ''} {artist or ''}".lower()
        combined = re.sub(r"[^\w\s]", "", combined)
        combined = re.sub(r"\s+", " ", combined).strip()
        return combined

    def _normalize_search_text(self, text):
        normalized = str(text or '').lower()
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _source_name(self, source):
        return self.SOURCE_LABELS.get(source, source.title() if source else 'Unknown')

    def _sorted_playlist_items(self):
        def sort_key(item):
            playlist_key, pl_data = item
            return (
                self._normalize_search_text(pl_data.get('name', '')),
                self._normalize_search_text(self._source_name(pl_data.get('source', 'youtube'))),
                str(playlist_key).lower()
            )

        return sorted(self.saved_playlists.items(), key=sort_key)

    def _build_source_logo_images(self):
        return {
            'sidebar': {
                'youtube': self._load_logo_image('youtube_18.png', 18, '#ff0000'),
                'spotify': self._load_logo_image('spotify_18.png', 18, '#1db954')
            },
            'table': {
                'youtube': self._load_logo_image('youtube_24.png', 24, '#ff0000'),
                'spotify': self._load_logo_image('spotify_24.png', 24, '#1db954'),
                'mixed': self._load_logo_image('mixed_24.png', 24, '#777777')
            }
        }

    def _load_logo_image(self, filename, size, fallback_color):
        logo_path = self.ASSETS_DIR / filename
        if logo_path.exists():
            return tk.PhotoImage(file=str(logo_path))

        image = tk.PhotoImage(width=size, height=size)
        image.put(fallback_color, to=(0, 0, size, size))
        return image

    def _source_logo_image(self, source, size='table'):
        images = self.source_logo_images.get(size, self.source_logo_images['table'])
        return images.get(source, self.source_logo_images['table'].get('mixed'))

    def _source_logo_for_sources(self, sources):
        if len(sources) == 1:
            return self._source_logo_image(next(iter(sources)))
        return self.source_logo_images['table']['mixed']

    def _create_source_badge(self, parent, source):
        return ttk.Label(parent, image=self._source_logo_image(source, size='sidebar'))

    def _focus_widget(self, widget):
        try:
            if widget is not None and widget.winfo_exists():
                widget.focus_set()
                if isinstance(widget, ttk.Entry):
                    widget.selection_range(0, tk.END)
                return "break"
        except tk.TclError:
            pass
        return self._focus_sidebar_search()

    def _focus_sidebar_search(self, _event=None):
        try:
            self.search_entry.focus_set()
            self.search_entry.selection_range(0, tk.END)
        except tk.TclError:
            pass
        return "break"

    def _focus_active_find_or_sidebar(self, _event=None):
        if self.active_find_entry is not None:
            try:
                if self.active_find_entry.winfo_exists():
                    return self._focus_widget(self.active_find_entry)
            except tk.TclError:
                self.active_find_entry = None
        return self._focus_sidebar_search()

    def _register_display_find_entry(self, parent, find_entry):
        self.active_find_entry = find_entry
        top_level = parent.winfo_toplevel()

        def focus_find(_event=None):
            return self._focus_widget(find_entry)

        top_level.bind("<Control-f>", focus_find)
        top_level.bind("<Command-f>", focus_find)

    def _create_display_find_controls(self, parent, find_var):
        find_label = ttk.Label(parent, text="Find:")
        find_entry = ttk.Entry(parent, textvariable=find_var, width=24)
        find_entry.bind("<Escape>", lambda _event: (find_var.set(""), "break")[-1])
        self._register_display_find_entry(parent, find_entry)
        return find_label, find_entry

    def _matches_find_query(self, values, query):
        terms = [term for term in self._normalize_search_text(query).split() if term]
        if not terms:
            return True

        haystack = self._normalize_search_text(" ".join(str(value or "") for value in values))
        return all(term in haystack for term in terms)

    def _selected_tree_entry(self, tree, entry_by_item):
        selected_items = tree.selection()
        if not selected_items:
            return None
        return entry_by_item.get(selected_items[0])

    def _show_selected_entry_details(self, tree, entry_by_item):
        entry = self._selected_tree_entry(tree, entry_by_item)
        if not entry:
            messagebox.showinfo("No Selection", "Select a song first.")
            return
        self.show_song_details_window(entry)

    def _play_selected_tree_entry(self, tree, entry_by_item):
        entry = self._selected_tree_entry(tree, entry_by_item)
        if not entry:
            messagebox.showinfo("No Selection", "Select a song first.")
            return
        self._play_entry(entry)

    def _create_info_window(self, title, geometry="760x560", minsize=(660, 420)):
        info_window = tk.Toplevel(self.root)
        info_window.title(title)
        info_window.geometry(geometry)
        info_window.minsize(*minsize)
        self._configure_window_icon(info_window)

        outer_frame = ttk.Frame(info_window, padding="18")
        outer_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        outer_frame.columnconfigure(0, weight=1)
        outer_frame.rowconfigure(1, weight=1)

        content_canvas = tk.Canvas(outer_frame, borderwidth=0, highlightthickness=0)
        y_scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=content_canvas.yview)
        content_frame = ttk.Frame(content_canvas)
        content_window = content_canvas.create_window((0, 0), window=content_frame, anchor=tk.NW)
        content_canvas.configure(yscrollcommand=y_scrollbar.set)

        def update_scroll_region(_event=None):
            content_canvas.configure(scrollregion=content_canvas.bbox("all"))

        def update_content_width(event):
            content_canvas.itemconfigure(content_window, width=event.width)

        content_frame.bind("<Configure>", update_scroll_region)
        content_canvas.bind("<Configure>", update_content_width)
        content_canvas.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        y_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))

        info_window.columnconfigure(0, weight=1)
        info_window.rowconfigure(0, weight=1)
        return info_window, outer_frame, content_frame

    def _add_info_header(self, parent, title, subtitle=None, actions=None):
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 14))
        header_frame.columnconfigure(0, weight=1)

        title_label = ttk.Label(header_frame, text=title, font=("Helvetica", 15, "bold"))
        title_label.grid(row=0, column=0, sticky=tk.W)

        if subtitle:
            subtitle_label = ttk.Label(header_frame, text=subtitle)
            subtitle_label.grid(row=1, column=0, sticky=tk.W, pady=(2, 0))

        if actions:
            action_frame = ttk.Frame(header_frame)
            action_frame.grid(row=0, column=1, rowspan=2, sticky=tk.E, padx=(12, 0))
            for index, (label, command) in enumerate(actions):
                button = ttk.Button(action_frame, text=label, command=command)
                button.grid(row=0, column=index, padx=(0 if index == 0 else 6, 0))

    def _add_info_section(self, parent, title, row):
        title_label = ttk.Label(parent, text=title, font=("Helvetica", 12, "bold"))
        title_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(14, 6))
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.grid(row=row + 1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 6))
        return row + 2

    def _add_info_row(self, parent, row, label, value, action=None):
        label_widget = ttk.Label(parent, text=f"{label}:", width=18, anchor=tk.E)
        label_widget.grid(row=row, column=0, sticky=tk.NE, padx=(0, 14), pady=3)

        value_frame = ttk.Frame(parent)
        value_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)
        value_frame.columnconfigure(0, weight=1)

        value_widget = ttk.Label(value_frame, text=str(value), wraplength=520, justify=tk.LEFT)
        value_widget.grid(row=0, column=0, sticky=(tk.W, tk.E))

        if action:
            action_label, command = action
            button = ttk.Button(value_frame, text=action_label, command=command)
            button.grid(row=0, column=1, sticky=tk.E, padx=(10, 0))

        return row + 1

    def show_song_details_window(self, entry):
        details_window, outer_frame, content_frame = self._create_info_window("Song Details")
        content_frame.columnconfigure(1, weight=1)

        self._add_info_header(
            outer_frame,
            entry.get('title', 'Unknown Title'),
            entry.get('artist', 'Unknown Artist'),
            actions=[
                ("Play", lambda: self._play_entry(entry)),
                ("Close", details_window.destroy)
            ]
        )

        row = 0
        row = self._add_info_section(content_frame, "General", row)
        row = self._add_info_row(content_frame, row, "Title", entry.get('title', 'Unknown Title'))
        row = self._add_info_row(content_frame, row, "Artist", entry.get('artist', 'Unknown Artist'))
        row = self._add_info_row(
            content_frame,
            row,
            "Sources",
            ", ".join(sorted(self._source_name(source) for source in entry.get('sources', []))) or "Unknown"
        )
        if self._show_youtube_queue_actions():
            row = self._add_info_row(content_frame, row, "Playback", self._entry_queue_status(entry))

        row = self._add_info_section(content_frame, "Playlist Appearances", row)
        summaries = self._entry_playlist_occurrence_summaries(entry)
        if not summaries:
            row = self._add_info_row(content_frame, row, "Playlists", "Unknown")

        for summary in summaries:
            count = summary.get('count') or 1
            occurrence_text = "1 occurrence" if count == 1 else f"{count} occurrences"
            track_ids = ", ".join(summary.get('track_ids') or [])
            row = self._add_info_row(
                content_frame,
                row,
                summary['label'],
                f"{occurrence_text}; Track IDs: {track_ids or 'Unknown'}",
                action=("Open", lambda link=summary['urls'][0]: self._open_external_url(link)) if summary.get('urls') else None
            )

    def _clear_display_frame(self):
        for child in self.display_frame.winfo_children():
            child.destroy()

    def _open_display_window(self, title, build_display, geometry="1080x680"):
        display_window = tk.Toplevel(self.root)
        display_window.title(title)
        display_window.geometry(geometry)
        self._configure_window_icon(display_window)

        display_frame = ttk.Frame(display_window, padding="20")
        display_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        display_window.columnconfigure(0, weight=1)
        display_window.rowconfigure(0, weight=1)

        build_display(display_frame)
        return display_window

    def _show_display(self, title, build_display, geometry="1080x680"):
        if self.use_display_windows_var.get():
            self._open_display_window(title, build_display, geometry=geometry)
            if self.current_display_view != 'playlist_selection':
                self.show_playlist_selection_display()
            return

        self._clear_display_frame()
        build_display(self.display_frame)

    def _active_playlist_vars(self):
        if self.use_display_windows_var.get() and self.display_playlist_vars:
            return self.display_playlist_vars
        return self.sidebar_playlist_vars

    def _selected_playlist_keys_from_active_display(self):
        return self._selected_playlist_keys(self._active_playlist_vars())

    def _on_display_mode_changed(self):
        selected_keys = set(self._selected_playlist_keys_from_active_display())
        if self.use_display_windows_var.get():
            self.playlist_selector_container.grid_remove()
            self.sidebar_selection_actions.grid_remove()
            self.show_playlist_selection_display(selected_keys=selected_keys)
            return

        self.display_playlist_vars = []
        self.playlist_selector_container.grid()
        self.sidebar_selection_actions.grid()
        self.refresh_sidebar_playlists(selected_keys=selected_keys)
        self.show_empty_display()

    def show_empty_display(self):
        self.current_display_view = 'empty'
        self._active_combined_refresh = None
        self.active_find_entry = None
        self._clear_display_frame()

        empty_frame = ttk.Frame(self.display_frame)
        empty_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        empty_frame.columnconfigure(0, weight=1)
        empty_frame.rowconfigure(0, weight=1)

        empty_label = ttk.Label(empty_frame, text="Choose an action from the sidebar.", font=("Helvetica", 13))
        empty_label.grid(row=0, column=0)

        self.display_frame.columnconfigure(0, weight=1)
        self.display_frame.rowconfigure(0, weight=1)

    def refresh_sidebar_playlists(self, selected_keys=None):
        for child in self.playlist_selector_container.winfo_children():
            child.destroy()

        self.sidebar_playlist_vars = self._build_playlist_checkbox_selector(
            self.playlist_selector_container,
            on_change=self._on_sidebar_playlist_changed,
            selected_keys=selected_keys
        )

    def refresh_playlist_selectors(self, selected_keys=None):
        self.refresh_sidebar_playlists(selected_keys=selected_keys)
        if self.use_display_windows_var.get():
            self.show_playlist_selection_display(selected_keys=selected_keys)

    def _selected_sidebar_playlist_keys(self):
        return self._selected_playlist_keys_from_active_display()

    def _on_sidebar_playlist_changed(self):
        if getattr(self, 'current_display_view', None) == 'combined':
            refresh = getattr(self, '_active_combined_refresh', None)
            if refresh:
                refresh()

    def _refresh_live_combined_if_active(self):
        if getattr(self, 'current_display_view', None) == 'combined':
            refresh = getattr(self, '_active_combined_refresh', None)
            if refresh:
                refresh()

    def show_settings_display(self):
        def build_settings_display(parent):
            self.current_display_view = 'settings'
            parent.columnconfigure(0, weight=1)

            title = ttk.Label(parent, text="Settings", font=("Helvetica", 15, "bold"))
            title.grid(row=0, column=0, sticky=tk.W, pady=(0, 14))

            display_frame = ttk.LabelFrame(parent, text="Display", padding="12")
            display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
            display_frame.columnconfigure(0, weight=1)

            display_window_setting = ttk.Checkbutton(
                display_frame,
                text="Open display output in separate windows",
                variable=self.use_display_windows_var,
                command=self._on_display_mode_changed
            )
            display_window_setting.grid(row=0, column=0, sticky=tk.W)

            description = ttk.Label(
                display_frame,
                text=(
                    "When enabled, search results, saved playlists, combined songs, "
                    "duplicate results, and settings open in windows. The main display "
                    "is used for playlist selection."
                ),
                wraplength=520
            )
            description.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))

            account_frame = ttk.LabelFrame(parent, text="YouTube Music Account", padding="12")
            account_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(12, 0))
            account_frame.columnconfigure(0, weight=1)

            status_label = ttk.Label(account_frame, text=f"Status: {self._youtube_music_auth_status()}")
            status_label.grid(row=0, column=0, sticky=tk.W)

            temp_records = self.youtube_account.load_temporary_playlists()
            temp_label = ttk.Label(
                account_frame,
                text=f"Temporary playlists waiting for cleanup: {len(temp_records)}"
            )
            temp_label.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))

            account_actions = ttk.Frame(account_frame)
            account_actions.grid(row=0, column=1, rowspan=2, sticky=tk.E, padx=(12, 0))

            connect_button = ttk.Button(
                account_actions,
                text="Reconnect" if self._is_youtube_music_connected() else "Connect",
                command=self.show_youtube_music_auth_display
            )
            connect_button.grid(row=0, column=0, sticky=tk.E, padx=(0, 6))

            disconnect_button = ttk.Button(
                account_actions,
                text="Disconnect",
                command=self.disconnect_youtube_music
            )
            disconnect_button.grid(row=0, column=1, sticky=tk.E, padx=(0, 6))
            if not self._is_youtube_music_connected():
                disconnect_button.state(["disabled"])

            cleanup_button = ttk.Button(
                account_actions,
                text="Delete Temporary",
                command=self.delete_temporary_youtube_playlists
            )
            cleanup_button.grid(row=0, column=2, sticky=tk.E)
            if not temp_records:
                cleanup_button.state(["disabled"])

            updates_frame = ttk.LabelFrame(parent, text="Updates", padding="12")
            updates_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(12, 0))
            updates_frame.columnconfigure(0, weight=1)

            version_label = ttk.Label(updates_frame, text=f"Current version: {APP_VERSION}")
            version_label.grid(row=0, column=0, sticky=tk.W)

            check_button = ttk.Button(
                updates_frame,
                text="Check for Updates",
                command=lambda: self.check_for_updates(silent=False)
            )
            check_button.grid(row=0, column=1, sticky=tk.E, padx=(12, 0))

        self._show_display("Settings", build_settings_display, geometry="760x460")

    def show_youtube_music_auth_display(self):
        self._show_display("Connect YouTube Music", self._build_youtube_music_auth_display, geometry="820x620")

    def _build_youtube_music_auth_display(self, parent):
        self.current_display_view = 'youtube_auth'
        parent.columnconfigure(0, weight=1)

        saved_credentials = self.youtube_account.load_client_credentials() or {}
        client_id_var = tk.StringVar(value=saved_credentials.get("client_id", ""))
        client_secret_var = tk.StringVar(value=saved_credentials.get("client_secret", ""))
        status_var = tk.StringVar(value=f"Status: {self._youtube_music_auth_status()}")
        code_var = tk.StringVar(value="No sign-in code yet")
        url_var = tk.StringVar(value="")

        title = ttk.Label(parent, text="Connect YouTube Music", font=("Helvetica", 15, "bold"))
        title.grid(row=0, column=0, sticky=tk.W, pady=(0, 12))

        intro = ttk.Label(
            parent,
            text=(
                "YouTube Music queue creation uses ytmusicapi OAuth. Create a TV and Limited Input OAuth client "
                "in Google Cloud once, paste its client ID and secret here, then sign in with the code."
            ),
            wraplength=720
        )
        intro.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 12))

        setup_frame = ttk.LabelFrame(parent, text="One-Time Google Setup", padding="12")
        setup_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
        setup_frame.columnconfigure(0, weight=1)

        setup_text = ttk.Label(
            setup_frame,
            text=(
                "Enable the YouTube Data API, then create an OAuth Client ID with application type "
                "\"TVs and Limited Input devices\". Desktop OAuth clients will fail with this sign-in flow. "
                "If your OAuth app is External and in Testing mode, add your Google account under "
                "Audience > Test users. Copy the TV client ID and client secret below."
            ),
            wraplength=700
        )
        setup_text.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 8))

        api_button = ttk.Button(
            setup_frame,
            text="Open YouTube Data API",
            command=lambda: self._open_external_url("https://console.cloud.google.com/apis/library/youtube.googleapis.com")
        )
        api_button.grid(row=1, column=0, sticky=tk.W, padx=(0, 8))

        credentials_button = ttk.Button(
            setup_frame,
            text="Open Credentials",
            command=lambda: self._open_external_url("https://console.cloud.google.com/apis/credentials")
        )
        credentials_button.grid(row=1, column=1, sticky=tk.W, padx=(0, 8))

        help_button = ttk.Button(
            setup_frame,
            text="OAuth Help",
            command=lambda: self._open_external_url("https://ytmusicapi.readthedocs.io/en/stable/setup/oauth.html")
        )
        help_button.grid(row=1, column=2, sticky=tk.W)

        audience_button = ttk.Button(
            setup_frame,
            text="Open Audience",
            command=lambda: self._open_external_url("https://console.cloud.google.com/auth/audience")
        )
        audience_button.grid(row=1, column=3, sticky=tk.W, padx=(8, 0))

        credentials_frame = ttk.LabelFrame(parent, text="OAuth Client", padding="12")
        credentials_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
        credentials_frame.columnconfigure(1, weight=1)

        client_id_label = ttk.Label(credentials_frame, text="Client ID:")
        client_id_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=(0, 6))
        client_id_entry = ttk.Entry(credentials_frame, textvariable=client_id_var)
        client_id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 6))

        client_secret_label = ttk.Label(credentials_frame, text="Client secret:")
        client_secret_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 8))
        client_secret_entry = ttk.Entry(credentials_frame, textvariable=client_secret_var, show="*")
        client_secret_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))

        sign_in_frame = ttk.LabelFrame(parent, text="Sign In", padding="12")
        sign_in_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
        sign_in_frame.columnconfigure(0, weight=1)

        status_label = ttk.Label(sign_in_frame, textvariable=status_var)
        status_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))

        code_label = ttk.Label(sign_in_frame, textvariable=code_var, font=("Helvetica", 18, "bold"))
        code_label.grid(row=1, column=0, sticky=tk.W)

        copy_button = ttk.Button(
            sign_in_frame,
            text="Copy Code",
            command=lambda: self._copy_to_clipboard(code_var.get())
        )
        copy_button.grid(row=1, column=1, sticky=tk.W, padx=(12, 6))

        def open_current_sign_in_url():
            sign_in_url = url_var.get().strip()
            if not sign_in_url:
                status_var.set("Status: click Save and Start Sign-In first to request a code.")
                return

            opened = self._open_external_url(sign_in_url)
            if opened:
                status_var.set("Status: sign-in page opened. Finish Google sign-in in the browser.")
            else:
                status_var.set("Status: could not open the browser automatically. Copy the URL below.")

        open_sign_in_button = ttk.Button(
            sign_in_frame,
            text="Open Sign-In Page",
            command=open_current_sign_in_url
        )
        open_sign_in_button.grid(row=1, column=2, sticky=tk.W)
        open_sign_in_button.state(["disabled"])

        url_entry = ttk.Entry(sign_in_frame, textvariable=url_var, state="readonly")
        url_entry.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(8, 0))

        start_button = ttk.Button(
            parent,
            text="Save and Start Sign-In",
            command=lambda: self._start_youtube_music_oauth_flow(
                client_id_var.get(),
                client_secret_var.get(),
                status_var,
                code_var,
                url_var,
                start_button,
                open_sign_in_button,
            )
        )
        start_button.grid(row=5, column=0, sticky=tk.W)

    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _start_youtube_music_oauth_flow(
        self,
        client_id,
        client_secret,
        status_var,
        code_var,
        url_var,
        start_button=None,
        open_sign_in_button=None,
    ):
        try:
            self.youtube_account.save_client_credentials(client_id, client_secret)
        except ValueError as e:
            messagebox.showwarning("Missing OAuth Details", str(e))
            return

        code_var.set("Requesting code...")
        url_var.set("")
        status_var.set("Status: requesting a Google sign-in code...")
        if start_button:
            start_button.state(["disabled"])
        if open_sign_in_button:
            open_sign_in_button.state(["disabled"])

        def worker():
            try:
                code = self.youtube_account.request_device_code()
            except Exception as e:
                self.root.after(0, lambda error=e: self._finish_youtube_oauth_error(status_var, start_button, error))
                return

            self.root.after(
                0,
                lambda: self._begin_youtube_oauth_polling(
                    code,
                    status_var,
                    code_var,
                    url_var,
                    start_button,
                    open_sign_in_button,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _format_youtube_oauth_error(self, error):
        error_text = str(error)
        if isinstance(error, BadOAuthClient) or "OAuth client failure" in error_text:
            return (
                "OAuth client failure. For ytmusicapi, create an OAuth Client ID with application type "
                "\"TVs and Limited Input devices\". Desktop OAuth clients will fail here."
            )

        if "access_denied" in error_text or "developer-approved testers" in error_text:
            return (
                "Access denied. In Google Cloud, open Google Auth Platform > Audience and add the "
                "Google account you are signing in with under Test users. Then start sign-in again."
            )

        return error_text

    def _finish_youtube_oauth_error(self, status_var, start_button, error):
        status_var.set(f"Status: sign-in failed - {self._format_youtube_oauth_error(error)}")
        if start_button:
            start_button.state(["!disabled"])

    def _begin_youtube_oauth_polling(
        self,
        code,
        status_var,
        code_var,
        url_var,
        start_button,
        open_sign_in_button,
    ):
        if code.get("error"):
            error_message = code.get("error_description") or code.get("error")
            self._finish_youtube_oauth_error(status_var, start_button, error_message)
            return

        user_code = code.get("user_code", "")
        verification_url = code.get("verification_url", "")
        sign_in_url = f"{verification_url}?user_code={user_code}" if verification_url and user_code else verification_url
        code_var.set(user_code or "Code unavailable")
        url_var.set(sign_in_url or "")
        if open_sign_in_button and sign_in_url:
            open_sign_in_button.state(["!disabled"])

        opened = self._open_external_url(sign_in_url) if sign_in_url else False
        if opened:
            status_var.set("Status: browser opened. Finish Google sign-in; the app will continue automatically.")
        else:
            status_var.set("Status: sign-in code ready. Click Open Sign-In Page or copy the URL.")
        interval = max(1, int(code.get("interval") or 5))
        expires_at = time.time() + int(code.get("expires_in") or 900)
        self._poll_youtube_oauth_token(
            code.get("device_code"),
            interval,
            expires_at,
            status_var,
            start_button,
        )

    def _poll_youtube_oauth_token(self, device_code, interval, expires_at, status_var, start_button):
        if not device_code:
            self._finish_youtube_oauth_error(status_var, start_button, "Google did not return a device code.")
            return

        if time.time() > expires_at:
            self._finish_youtube_oauth_error(status_var, start_button, "the sign-in code expired.")
            return

        def worker():
            try:
                response = self.youtube_account.token_from_device_code(device_code)
            except Exception as e:
                self.root.after(0, lambda error=e: self._finish_youtube_oauth_error(status_var, start_button, error))
                return

            self.root.after(
                0,
                lambda: self._handle_youtube_oauth_token_response(
                    response,
                    device_code,
                    interval,
                    expires_at,
                    status_var,
                    start_button,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _handle_youtube_oauth_token_response(
        self,
        response,
        device_code,
        interval,
        expires_at,
        status_var,
        start_button,
    ):
        response = response or {}
        if response.get("access_token"):
            try:
                self.youtube_account.store_token(response)
                self.authenticated_ytmusic = self._build_authenticated_ytmusic()
                if self.authenticated_ytmusic is None:
                    raise RuntimeError("The saved token could not initialize a YouTube Music session.")
            except Exception as e:
                self._finish_youtube_oauth_error(status_var, start_button, e)
                return

            status_var.set("Status: connected to YouTube Music.")
            if start_button:
                start_button.state(["!disabled"])
            messagebox.showinfo("YouTube Music Connected", "YouTube Music is connected. You can now create temporary queue playlists.")
            return

        error = response.get("error")
        if error in {"authorization_pending", "slow_down"}:
            next_interval = interval + 5 if error == "slow_down" else interval
            self.root.after(
                next_interval * 1000,
                lambda: self._poll_youtube_oauth_token(
                    device_code,
                    next_interval,
                    expires_at,
                    status_var,
                    start_button,
                )
            )
            return

        self._finish_youtube_oauth_error(status_var, start_button, error or response)

    def disconnect_youtube_music(self):
        if not self._is_youtube_music_connected():
            messagebox.showinfo("YouTube Music Account", "YouTube Music is not connected.")
            return

        should_disconnect = messagebox.askyesno(
            "Disconnect YouTube Music",
            "Remove the saved YouTube Music sign-in token from this computer?"
        )
        if not should_disconnect:
            return

        self.youtube_account.disconnect()
        self.authenticated_ytmusic = None
        messagebox.showinfo("YouTube Music Account", "YouTube Music has been disconnected.")
        self.show_settings_display()

    def _find_matching_tracks(self, query):
        query_terms = [term for term in self._normalize_search_text(query).split() if term]
        if not query_terms:
            return {}

        matches = {}
        for pl_id, pl_data in self.saved_playlists.items():
            playlist_name = pl_data.get('name', f'Playlist {pl_id}')
            source = pl_data.get('source', 'youtube')
            source_label = f"{self._source_name(source)}: {playlist_name}"
            for track in pl_data.get('tracks', []):
                title = track.get('title', '')
                artist = track.get('artist', '')
                searchable_text = self._normalize_search_text(f"{title} {artist}")

                if all(term in searchable_text for term in query_terms):
                    track_key = self._normalize_song_key(title, artist)
                    if not track_key:
                        continue

                    if track_key not in matches:
                        matches[track_key] = {
                            'track': track,
                            'playlists': set()
                        }
                    matches[track_key]['playlists'].add(source_label)

        return matches

    def _playlist_label(self, playlist_key, pl_data):
        return pl_data.get('name', f'Playlist {playlist_key}')

    def _playlist_source_label(self, source, playlist_label):
        return f"{self._source_name(source)}: {playlist_label}"

    def _track_play_url(self, source, track):
        track_id = track.get('id') or track.get('trackId') or track.get('videoId')
        if source == 'youtube':
            video_id = track.get('videoId') or track_id
            if video_id:
                return f"https://music.youtube.com/watch?v={video_id}"
        if source == 'spotify':
            spotify_id = track.get('trackId') or track_id
            if spotify_id:
                if str(spotify_id).startswith('spotify:track:'):
                    spotify_id = str(spotify_id).rsplit(':', 1)[1]
                return f"https://open.spotify.com/track/{spotify_id}"
        return None

    def _playlist_url(self, source, playlist_id):
        if not playlist_id:
            return None
        if source == 'youtube':
            return f"https://music.youtube.com/playlist?list={playlist_id}"
        if source == 'spotify':
            return f"https://open.spotify.com/playlist/{playlist_id}"
        return None

    def _track_youtube_video_id(self, source, track):
        if source != 'youtube' or not isinstance(track, dict):
            return None
        video_id = track.get('videoId') or track.get('id')
        return str(video_id) if video_id else None

    def _computed_youtube_track_queue_status(self, source, track):
        if source != 'youtube':
            return "External"
        if not isinstance(track, dict) or not self._track_youtube_video_id(source, track):
            return "No video ID"
        if track.get('isAvailable') is False:
            return "Unavailable"

        video_type = track.get('videoType') or track.get('musicVideoType')
        if video_type in self.YOUTUBE_MUSIC_ONLY_TYPES:
            return "YTM only"
        if video_type:
            return "Queue OK"
        return "Unknown"

    def _youtube_queue_marker(self, source, track):
        status = self._computed_youtube_track_queue_status(source, track)
        return {
            'queueStatus': status,
            'queuePlayable': status in self.YOUTUBE_QUEUE_PLAYABLE_STATUSES
        }

    def _youtube_track_queue_status(self, source, track):
        if source != 'youtube':
            return "External"
        if not isinstance(track, dict) or not self._track_youtube_video_id(source, track):
            return "No video ID"

        stored_status = track.get('queueStatus')
        if track.get('queuePlayable') is False:
            return stored_status or "Unavailable"
        if stored_status in {"Unavailable", "YTM only", "No video ID"}:
            return stored_status

        return self._computed_youtube_track_queue_status(source, track)

    def _youtube_track_queue_playable(self, source, track):
        return self._youtube_track_queue_status(source, track) in self.YOUTUBE_QUEUE_PLAYABLE_STATUSES

    def _entry_queue_status(self, entry):
        statuses = []
        has_youtube = False
        for appearance in entry.get('appearances', []):
            source = appearance.get('source')
            if source != 'youtube':
                continue

            has_youtube = True
            status = self._youtube_track_queue_status(source, appearance.get('track', {}))
            statuses.append(status)
            if status == "Queue OK":
                return "Queue OK"

        if "Unknown" in statuses:
            return "Unknown"
        if "YTM only" in statuses:
            return "YTM only"
        if "Unavailable" in statuses:
            return "Unavailable"
        track = entry.get('track') if isinstance(entry.get('track'), dict) else None
        if track:
            return self._youtube_track_queue_status(track.get('source'), track)
        return "External" if not has_youtube else "No video ID"

    def _youtube_queue_track_from_entry(self, entry):
        # Merged rows can contain both sources; only YouTube has queue playback without OAuth.
        appearances = entry.get('appearances', [])
        for appearance in appearances:
            source = appearance.get('source')
            track = appearance.get('track', {})
            video_id = self._track_youtube_video_id(source, track)
            if not video_id or not self._youtube_track_queue_playable(source, track):
                continue

            return {
                'videoId': video_id,
                'title': entry.get('title') or track.get('title') or 'Unknown Title',
                'artist': entry.get('artist') or track.get('artist') or 'Unknown Artist',
                'playlist': self._playlist_source_label(source, appearance.get('playlist', 'Unknown Playlist')),
                'sourceUrl': self._track_play_url(source, track),
                'thumbnailUrl': track.get('thumbnailUrl') or self._best_thumbnail_url(track.get('thumbnails')),
                'playbackStatus': self._youtube_track_queue_status(source, track)
            }

        track = entry.get('track', {})
        source = track.get('source')
        video_id = self._track_youtube_video_id(source, track)
        if not video_id or not self._youtube_track_queue_playable(source, track):
            return None

        return {
            'videoId': video_id,
            'title': entry.get('title') or track.get('title') or 'Unknown Title',
            'artist': entry.get('artist') or track.get('artist') or 'Unknown Artist',
            'playlist': self._format_playlist_occurrences(entry, limit=None) or 'Unknown Playlist',
            'sourceUrl': self._track_play_url(source, track),
            'thumbnailUrl': track.get('thumbnailUrl') or self._best_thumbnail_url(track.get('thumbnails')),
            'playbackStatus': self._youtube_track_queue_status(source, track)
        }

    def _youtube_queue_tracks_from_entries(self, entries):
        queue_tracks = []
        seen_video_ids = set()
        for entry in entries:
            queue_track = self._youtube_queue_track_from_entry(entry)
            if not queue_track:
                continue

            video_id = queue_track['videoId']
            if video_id in seen_video_ids:
                continue

            queue_tracks.append(queue_track)
            seen_video_ids.add(video_id)

        return queue_tracks

    def _youtube_queue_tracks_from_playlist(self, playlist_key):
        pl_data = self.saved_playlists.get(playlist_key)
        if not pl_data:
            return []

        source, _playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
        if source != 'youtube':
            return []

        playlist_name = pl_data.get('name', 'Unnamed Playlist')
        queue_tracks = []
        tracks = pl_data.get('tracks') or self._fallback_youtube_tracks(pl_data.get('videos', set()))
        for track in tracks:
            video_id = self._track_youtube_video_id(source, track)
            if not video_id or not self._youtube_track_queue_playable(source, track):
                continue

            queue_tracks.append({
                'videoId': video_id,
                'title': track.get('title') or 'Unknown Title',
                'artist': track.get('artist') or 'Unknown Artist',
                'playlist': self._playlist_source_label(source, playlist_name),
                'sourceUrl': self._track_play_url(source, track),
                'thumbnailUrl': track.get('thumbnailUrl') or self._best_thumbnail_url(track.get('thumbnails')),
                'playbackStatus': self._youtube_track_queue_status(source, track)
            })

        return queue_tracks

    def _open_youtube_queue_player(self, title, queue_tracks):
        if not queue_tracks:
            messagebox.showinfo(
                "YouTube Queue",
                "No YouTube tracks are available for this queue. Spotify queue playback requires Spotify OAuth, so Spotify is limited to external links for now."
            )
            return

        try:
            # The player module prefers a native pywebview window and falls back to a browser tab.
            self.youtube_player.open_queue(title, queue_tracks)
        except Exception as e:
            messagebox.showerror("YouTube Player", f"Failed to start the YouTube player: {e}")

    def _play_entries_as_youtube_queue(self, entries, title):
        self._open_youtube_queue_player(title, self._youtube_queue_tracks_from_entries(entries))

    def _show_youtube_queue_actions(self):
        value = os.environ.get(self.YOUTUBE_QUEUE_ACTIONS_ENV_VAR, "")
        return value.lower() in {"1", "true", "yes", "on"}

    def _youtube_playlist_sources_from_keys(self, playlist_keys):
        youtube_playlists = []
        skipped_playlists = []
        for playlist_key in playlist_keys:
            pl_data = self.saved_playlists.get(playlist_key)
            if not pl_data:
                continue

            source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
            playlist_info = {
                'key': playlist_key,
                'id': playlist_id,
                'name': pl_data.get('name', 'Unnamed Playlist'),
                'source': source
            }
            if source == 'youtube':
                youtube_playlists.append(playlist_info)
            else:
                skipped_playlists.append(playlist_info)

        return youtube_playlists, skipped_playlists

    def play_selection_in_youtube_music(self):
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first.")
            return

        selected_playlist_keys = self._selected_sidebar_playlist_keys()
        if not selected_playlist_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist.")
            return

        youtube_playlists, skipped_playlists = self._youtube_playlist_sources_from_keys(selected_playlist_keys)
        if not youtube_playlists:
            messagebox.showinfo(
                "YouTube Music",
                "Only YouTube Music playlists can be used for this queue right now. Spotify playlists were not added."
            )
            return

        if skipped_playlists:
            should_continue = messagebox.askyesno(
                "Spotify Playlists Skipped",
                (
                    f"{len(skipped_playlists)} selected Spotify playlist"
                    f"{'' if len(skipped_playlists) == 1 else 's'} will be skipped for now.\n\n"
                    "Continue with the selected YouTube Music playlists?"
                )
            )
            if not should_continue:
                return

        if not self._is_youtube_music_connected():
            should_connect = messagebox.askyesno(
                "Connect YouTube Music",
                "Creating a temporary YouTube Music playlist requires sign-in. Connect YouTube Music now?"
            )
            if should_connect:
                self.show_youtube_music_auth_display()
            return

        self._create_temporary_youtube_music_playlist(youtube_playlists)

    def _create_temporary_youtube_music_playlist(self, youtube_playlists):
        client = self._youtube_music_client()
        if client is None:
            messagebox.showerror(
                "YouTube Music",
                "The saved YouTube Music sign-in could not be loaded. Please reconnect YouTube Music in Settings."
            )
            self.show_youtube_music_auth_display()
            return

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Creating YouTube Music Queue")
        progress_window.geometry("430x150")
        progress_window.resizable(False, False)
        self._configure_window_icon(progress_window)

        main_frame = ttk.Frame(progress_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)

        status_var = tk.StringVar(value="Creating private temporary playlist...")
        status_label = ttk.Label(main_frame, textvariable=status_var)
        status_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 12))

        progress_bar = ttk.Progressbar(main_frame, mode="indeterminate", length=320)
        progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        progress_bar.start(12)

        def worker():
            try:
                title, temp_playlist_id, skipped_video_ids = self._create_temporary_youtube_music_playlist_sync(
                    client,
                    youtube_playlists,
                    lambda text: self.root.after(0, lambda: status_var.set(text)),
                )
            except Exception as e:
                self.root.after(
                    0,
                    lambda error=e: self._finish_temporary_playlist_creation(progress_window, None, None, error)
                )
                return

            self.root.after(
                0,
                lambda: self._finish_temporary_playlist_creation(
                    progress_window,
                    title,
                    temp_playlist_id,
                    None,
                    skipped_video_ids,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _create_temporary_youtube_music_playlist_sync(self, client, youtube_playlists, set_status):
        timestamp = datetime.now().strftime("%Y-%m-%d %H.%M")
        title = f"Playlist Manager Queue {timestamp}"
        description = "Temporary private playlist created by YouTube Music Playlist Manager."
        video_ids = self._temporary_youtube_playlist_video_ids(youtube_playlists)
        if not video_ids:
            raise RuntimeError(
                "No cached YouTube songs were found in the selected playlists. Update the selected playlists, then try again."
            )

        temp_playlist_id, remaining_video_ids, seeded_count = self._create_seeded_temporary_youtube_playlist(
            client,
            title,
            description,
            video_ids,
            set_status,
        )

        try:
            added_count, skipped_video_ids = self._add_video_ids_to_temporary_youtube_playlist(
                client,
                temp_playlist_id,
                remaining_video_ids,
                set_status,
            )
        except Exception:
            self._delete_temporary_youtube_playlist_best_effort(client, temp_playlist_id)
            raise

        if seeded_count + added_count == 0:
            self._delete_temporary_youtube_playlist_best_effort(client, temp_playlist_id)
            raise RuntimeError("No songs could be added to the temporary playlist.")

        self.youtube_account.remember_temporary_playlist(
            temp_playlist_id,
            title,
            [
                {
                    "id": playlist["id"],
                    "name": playlist["name"],
                    "source": playlist["source"],
                }
                for playlist in youtube_playlists
            ]
        )
        return title, temp_playlist_id, skipped_video_ids

    def _create_seeded_temporary_youtube_playlist(self, client, title, description, video_ids, set_status):
        set_status("Creating private playlist...")
        try:
            temp_playlist_id = client.create_playlist(
                title,
                description,
                privacy_status="PRIVATE",
                video_ids=[video_ids[0]],
            )
            if not isinstance(temp_playlist_id, str) or not temp_playlist_id:
                raise RuntimeError(temp_playlist_id)
            return temp_playlist_id, video_ids[1:], 1
        except Exception as ytmusic_error:
            set_status("YouTube Music create failed; trying YouTube Data API...")
            try:
                data_api_client = self._youtube_data_api_client()
                temp_playlist_id = data_api_client.create_playlist(
                    title,
                    description,
                    privacy_status="private",
                )
                return temp_playlist_id, video_ids, 0
            except Exception as data_api_error:
                raise RuntimeError(
                    "Could not create the temporary playlist. "
                    f"YouTube Music error: {ytmusic_error}. "
                    f"YouTube Data API error: {data_api_error}"
                ) from data_api_error

    def _add_video_ids_to_temporary_youtube_playlist(self, client, temp_playlist_id, video_ids, set_status):
        added_count = 0
        skipped_video_ids = []
        chunks = list(self._chunks(video_ids, self.YOUTUBE_TEMP_PLAYLIST_CHUNK_SIZE))
        for index, chunk in enumerate(chunks, start=1):
            set_status(f"Adding songs {index} of {len(chunks)}...")
            added, skipped = self._add_video_id_chunk_adaptive(
                client,
                temp_playlist_id,
                chunk,
                set_status,
                f"batch {index} of {len(chunks)}",
            )
            added_count += added
            skipped_video_ids.extend(skipped)
        return added_count, skipped_video_ids

    def _add_video_id_chunk_adaptive(self, client, temp_playlist_id, video_ids, set_status, label):
        if not video_ids:
            return 0, []

        try:
            response = client.add_playlist_items(temp_playlist_id, videoIds=video_ids)
            if self._ytmusic_response_succeeded(response):
                return len(video_ids), []
            raise RuntimeError(response)
        except Exception as e:
            if len(video_ids) == 1:
                return 0, [{"video_id": video_ids[0], "error": str(e)}]

            middle = max(1, len(video_ids) // 2)
            set_status(f"Retrying smaller song groups from {label}...")
            left_added, left_skipped = self._add_video_id_chunk_adaptive(
                client,
                temp_playlist_id,
                video_ids[:middle],
                set_status,
                label,
            )
            right_added, right_skipped = self._add_video_id_chunk_adaptive(
                client,
                temp_playlist_id,
                video_ids[middle:],
                set_status,
                label,
            )
            return left_added + right_added, left_skipped + right_skipped

    def _delete_temporary_youtube_playlist_best_effort(self, client, playlist_id):
        with contextlib.suppress(Exception):
            client.delete_playlist(playlist_id)
            return

        with contextlib.suppress(Exception):
            self._youtube_data_api_client().delete_playlist(playlist_id)

    def _temporary_youtube_playlist_video_ids(self, youtube_playlists):
        video_entries = []
        for playlist in youtube_playlists:
            pl_data = self.saved_playlists.get(playlist.get('key'), {})
            tracks = pl_data.get('tracks') if isinstance(pl_data.get('tracks'), list) else []
            if tracks:
                for track in tracks:
                    if not isinstance(track, dict):
                        continue
                    video_id = str(track.get('videoId') or track.get('id') or "").strip()
                    if video_id:
                        video_entries.append((video_id, self._is_preferred_temporary_playlist_seed(track)))
                continue

            for video_id in sorted(self._coerce_id_set(pl_data.get('videos'))):
                video_entries.append((str(video_id), True))

        video_ids = [video_id for video_id, _preferred in video_entries]
        for index, (_video_id, preferred) in enumerate(video_entries):
            if preferred:
                return [video_ids[index]] + video_ids[:index] + video_ids[index + 1:]
        return video_ids

    def _is_preferred_temporary_playlist_seed(self, track):
        if not isinstance(track, dict):
            return True
        if track.get('queuePlayable') is False:
            return False
        if track.get('queueStatus') == "YTM only":
            return False
        if track.get('videoType') in self.YOUTUBE_MUSIC_ONLY_TYPES:
            return False
        return True

    def _chunks(self, items, size):
        if size <= 0:
            raise ValueError("Chunk size must be greater than zero.")
        for start in range(0, len(items), size):
            yield items[start:start + size]

    def _ytmusic_response_succeeded(self, response):
        if isinstance(response, str):
            return "SUCCEEDED" in response
        if isinstance(response, dict):
            return "SUCCEEDED" in str(response.get("status") or "")
        return False

    def _finish_temporary_playlist_creation(self, progress_window, title, temp_playlist_id, error, skipped_video_ids=None):
        if progress_window.winfo_exists():
            progress_window.destroy()

        if error:
            messagebox.showerror("YouTube Music", f"Failed to create the temporary playlist: {error}")
            return

        self.youtube_account.open_playlist(temp_playlist_id)
        skipped_video_ids = skipped_video_ids or []
        skipped_message = ""
        if skipped_video_ids:
            examples = ", ".join(item["video_id"] for item in skipped_video_ids[:5])
            more = "..." if len(skipped_video_ids) > 5 else ""
            skipped_message = (
                f"\n\nSkipped {len(skipped_video_ids)} song"
                f"{'' if len(skipped_video_ids) == 1 else 's'} that YouTube Music rejected"
                f" ({examples}{more})."
            )

        messagebox.showinfo(
            "YouTube Music Playlist Opened",
            (
                f"Created and opened {title}.\n\n"
                "When you are done listening, use Settings > Delete Temporary to remove it."
                f"{skipped_message}"
            )
        )

        if self.current_display_view == 'settings':
            self.show_settings_display()

    def delete_temporary_youtube_playlists(self, prompt=True):
        records = self.youtube_account.load_temporary_playlists()
        if not records:
            messagebox.showinfo("Temporary Playlists", "There are no temporary YouTube Music playlists to delete.")
            return

        client = self._youtube_music_client()
        if client is None:
            messagebox.showerror(
                "YouTube Music",
                "Reconnect YouTube Music before deleting temporary playlists."
            )
            self.show_youtube_music_auth_display()
            return

        if prompt:
            should_delete = messagebox.askyesno(
                "Delete Temporary Playlists",
                (
                    f"Delete {len(records)} temporary YouTube Music playlist"
                    f"{'' if len(records) == 1 else 's'} from your account?"
                )
            )
            if not should_delete:
                return

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Deleting Temporary Playlists")
        progress_window.geometry("430x150")
        progress_window.resizable(False, False)
        self._configure_window_icon(progress_window)

        main_frame = ttk.Frame(progress_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)

        status_var = tk.StringVar(value="Deleting temporary playlists...")
        status_label = ttk.Label(main_frame, textvariable=status_var)
        status_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 12))

        progress_bar = ttk.Progressbar(main_frame, mode="indeterminate", length=320)
        progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        progress_bar.start(12)

        def worker():
            deleted_ids = []
            failed = []
            for index, record in enumerate(records, start=1):
                self.root.after(
                    0,
                    lambda record=record, index=index: status_var.set(
                        f"Deleting {index} of {len(records)}: {record.title}"
                    )
                )
                try:
                    response = client.delete_playlist(record.playlist_id)
                    if isinstance(response, dict) and "status" in response and "SUCCEEDED" not in response["status"]:
                        raise RuntimeError(response)
                    deleted_ids.append(record.playlist_id)
                except Exception as e:
                    failed.append((record, e))

            self.root.after(
                0,
                lambda: self._finish_temporary_playlist_deletion(
                    progress_window,
                    deleted_ids,
                    failed,
                )
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_temporary_playlist_deletion(self, progress_window, deleted_ids, failed):
        if progress_window.winfo_exists():
            progress_window.destroy()

        if deleted_ids:
            self.youtube_account.forget_temporary_playlists(deleted_ids)

        if failed:
            messagebox.showwarning(
                "Temporary Playlist Cleanup",
                (
                    f"Deleted {len(deleted_ids)} playlist"
                    f"{'' if len(deleted_ids) == 1 else 's'}, but {len(failed)} could not be deleted."
                )
            )
        else:
            messagebox.showinfo(
                "Temporary Playlist Cleanup",
                f"Deleted {len(deleted_ids)} temporary playlist{'' if len(deleted_ids) == 1 else 's'}."
            )

        if self.current_display_view == 'settings':
            self.show_settings_display()

    def _play_playlist_youtube_queue(self, playlist_key):
        pl_data = self.saved_playlists.get(playlist_key)
        if not pl_data:
            messagebox.showinfo("No Selection", "Select a saved playlist first.")
            return

        source, _playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
        if source != 'youtube':
            messagebox.showinfo(
                "Spotify Playback Restricted",
                "Spotify queue playback requires Spotify OAuth, so Spotify playlists are limited to external links for now."
            )
            return

        playlist_name = pl_data.get('name', 'Unnamed Playlist')
        self._open_youtube_queue_player(
            playlist_name,
            self._youtube_queue_tracks_from_playlist(playlist_key)
        )

    def _open_playlist_url(self, playlist_key):
        pl_data = self.saved_playlists.get(playlist_key)
        if not pl_data:
            messagebox.showinfo("No Selection", "Select a saved playlist first.")
            return

        source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
        url = self._playlist_url(source, playlist_id)
        if not url:
            messagebox.showinfo("No Playlist Link", "No playable source link is available for this playlist.")
            return
        self._open_external_url(url)

    def _entry_play_url(self, entry):
        appearances = entry.get('appearances', [])
        for preferred_source in ('youtube', 'spotify'):
            for appearance in appearances:
                if appearance.get('source') == preferred_source:
                    url = self._track_play_url(preferred_source, appearance.get('track', {}))
                    if url:
                        return url

        for appearance in appearances:
            url = self._track_play_url(appearance.get('source'), appearance.get('track', {}))
            if url:
                return url
        for source in entry.get('sources', []):
            url = self._track_play_url(source, entry.get('track', {}))
            if url:
                return url
        return None

    def _open_entry_play_url(self, entry):
        url = self._entry_play_url(entry)
        if not url:
            messagebox.showinfo("No Playback Link", "No playable source link is available for this song.")
            return
        self._open_external_url(url)

    def _play_entry(self, entry):
        youtube_queue_tracks = self._youtube_queue_tracks_from_entries([entry])
        if youtube_queue_tracks:
            self._open_youtube_queue_player(entry.get('title', 'YouTube Queue'), youtube_queue_tracks)
            return

        self._open_entry_play_url(entry)

    def _entry_playlist_occurrence_labels(self, entry):
        labels = []
        for summary in self._entry_playlist_occurrence_summaries(entry):
            count = summary.get('count') or 1
            suffix = f" ({count})" if count > 1 else ""
            labels.append(f"{summary['label']}{suffix}")
        return labels

    def _entry_playlist_occurrence_summaries(self, entry):
        summaries = []
        grouped = {}

        for appearance in entry.get('appearances', []):
            source = appearance.get('source', 'youtube')
            playlist = appearance.get('playlist', 'Unknown Playlist')
            group_key = (source, playlist)
            if group_key not in grouped:
                grouped[group_key] = {
                    'label': self._playlist_source_label(source, playlist),
                    'count': 0,
                    'track_ids': [],
                    'urls': []
                }
                summaries.append(grouped[group_key])

            summary = grouped[group_key]
            summary['count'] += 1
            track = appearance.get('track', {})
            track_id = track.get('id') or track.get('trackId') or track.get('videoId')
            if track_id and track_id not in summary['track_ids']:
                summary['track_ids'].append(track_id)

            url = self._track_play_url(source, track)
            if url and url not in summary['urls']:
                summary['urls'].append(url)

        if summaries:
            return summaries

        return [
            {
                'label': playlist,
                'count': 1,
                'track_ids': [],
                'urls': []
            }
            for playlist in sorted(entry.get('playlists', []))
        ]

    def _format_playlist_occurrences(self, entry, limit=None):
        text = "; ".join(self._entry_playlist_occurrence_labels(entry))
        if limit is None or len(text) <= limit:
            return text
        return text[:max(0, limit - 3)].rstrip() + "..."

    def _cached_track_id_count(self, tracks):
        return len({
            track.get('id') or track.get('trackId') or track.get('videoId')
            for track in tracks
            if isinstance(track, dict) and (track.get('id') or track.get('trackId') or track.get('videoId'))
        })

    def _cached_queue_status_counts(self, source, tracks):
        counts = {}
        for track in tracks:
            status = self._youtube_track_queue_status(source, track)
            counts[status] = counts.get(status, 0) + 1
        return counts

    def show_playlist_details_window(self, playlist_key):
        pl_data = self.saved_playlists.get(playlist_key)
        if not pl_data:
            messagebox.showinfo("No Selection", "Select a saved playlist first.")
            return

        source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
        source_name = self._source_name(source)
        playlist_name = pl_data.get('name', 'Unnamed Playlist')
        videos = pl_data.get('videos', set())
        tracks = pl_data.get('tracks', [])
        playlist_url = self._playlist_url(source, playlist_id)

        details_window, outer_frame, content_frame = self._create_info_window("Playlist Info", geometry="720x500")
        content_frame.columnconfigure(1, weight=1)

        actions = []
        if source == 'youtube' and tracks and self._show_youtube_queue_actions():
            actions.append(("Play Queue", lambda: self._play_playlist_youtube_queue(playlist_key)))
        if playlist_url:
            actions.append(("Open", lambda: self._open_external_url(playlist_url)))
        actions.append(("Close", details_window.destroy))
        self._add_info_header(outer_frame, playlist_name, source_name, actions=actions)

        row = 0
        row = self._add_info_section(content_frame, "General", row)
        row = self._add_info_row(content_frame, row, "Name", playlist_name)
        row = self._add_info_row(content_frame, row, "Source", source_name)
        row = self._add_info_row(content_frame, row, "Playlist ID", playlist_id)
        row = self._add_info_row(content_frame, row, "Storage Key", playlist_key)
        row = self._add_info_row(
            content_frame,
            row,
            "Playlist Link",
            playlist_url or "Unavailable",
            action=("Open", lambda: self._open_external_url(playlist_url)) if playlist_url else None
        )

        row = self._add_info_section(content_frame, "Cached Data", row)
        row = self._add_info_row(content_frame, row, "Saved Item IDs", len(videos))
        row = self._add_info_row(content_frame, row, "Cached Tracks", len(tracks))
        row = self._add_info_row(content_frame, row, "Unique Cached Tracks", self._cached_track_id_count(tracks))
        row = self._add_info_row(content_frame, row, "Metadata Cached", "Yes" if tracks else "No")
        if source == 'youtube' and tracks and self._show_youtube_queue_actions():
            status_counts = self._cached_queue_status_counts(source, tracks)
            row = self._add_info_row(content_frame, row, "Queue-Playable Tracks", status_counts.get("Queue OK", 0) + status_counts.get("Unknown", 0))
            row = self._add_info_row(content_frame, row, "YTM-Only Tracks", status_counts.get("YTM only", 0))

        if tracks:
            first_track = tracks[0]
            last_track = tracks[-1]
            row = self._add_info_section(content_frame, "Track Snapshot", row)
            row = self._add_info_row(
                content_frame,
                row,
                "First Track",
                f"{first_track.get('title', 'Unknown Title')} - {first_track.get('artist', 'Unknown Artist')}"
            )
            row = self._add_info_row(
                content_frame,
                row,
                "Last Track",
                f"{last_track.get('title', 'Unknown Title')} - {last_track.get('artist', 'Unknown Artist')}"
            )

    def _combined_track_key(self, track):
        title = track.get('title', '')
        artist = track.get('artist', '')
        song_key = self._normalize_song_key(title, artist)
        if song_key:
            return song_key

        source = track.get('source', 'youtube')
        track_id = track.get('id') or track.get('trackId') or track.get('videoId')
        if track_id:
            return f"{source}:{track_id}"

        return None

    def _collect_combined_tracks(self, playlist_keys, merge_duplicates=True):
        combined = []
        merged_entries = {}

        for playlist_order, playlist_key in enumerate(playlist_keys):
            pl_data = self.saved_playlists.get(playlist_key)
            if not pl_data:
                continue

            source = pl_data.get('source', 'youtube')
            playlist_label = self._playlist_label(playlist_key, pl_data)
            for track_order, track in enumerate(pl_data.get('tracks', [])):
                if not isinstance(track, dict):
                    continue

                title = track.get('title') or 'Unknown Title'
                artist = track.get('artist') or 'Unknown Artist'
                entry_key = self._combined_track_key(track)
                if not entry_key:
                    entry_key = f"{playlist_key}:{track_order}"

                if not merge_duplicates:
                    entry_key = f"{playlist_key}:{track_order}:{entry_key}"

                # Keep each appearance so duplicate rows can show repeated playlist membership later.
                appearance = {
                    'playlist_key': playlist_key,
                    'playlist': playlist_label,
                    'source': source,
                    'track': track,
                    'playlist_order': playlist_order,
                    'track_order': track_order
                }

                if merge_duplicates and entry_key in merged_entries:
                    entry = merged_entries[entry_key]
                    entry['playlists'].add(playlist_label)
                    entry['sources'].add(source)
                    entry['appearances'].append(appearance)
                    entry['appearance_count'] += 1
                    continue

                entry = {
                    'key': entry_key,
                    'track': track,
                    'title': title,
                    'artist': artist,
                    'playlists': {playlist_label},
                    'sources': {source},
                    'appearances': [appearance],
                    'playlist_order': playlist_order,
                    'track_order': track_order,
                    'appearance_count': 1
                }
                combined.append(entry)
                if merge_duplicates:
                    merged_entries[entry_key] = entry

        return combined

    def _sort_combined_tracks(self, tracks, sort_label):
        sort_mode = self.COMBINED_SORT_OPTIONS.get(sort_label, sort_label)

        def normalized(value):
            return self._normalize_search_text(value)

        def playlist_name(entry):
            return normalized(next(iter(sorted(entry['playlists'])), ''))

        def source_name(entry):
            return normalized(next(iter(sorted(entry['sources'])), ''))

        sorters = {
            'title': lambda entry: (
                normalized(entry['title']),
                normalized(entry['artist']),
                entry['playlist_order'],
                entry['track_order']
            ),
            'artist': lambda entry: (
                normalized(entry['artist']),
                normalized(entry['title']),
                entry['playlist_order'],
                entry['track_order']
            ),
            'playlist': lambda entry: (
                playlist_name(entry),
                entry['playlist_order'],
                entry['track_order'],
                normalized(entry['title'])
            ),
            'source': lambda entry: (
                source_name(entry),
                normalized(entry['title']),
                normalized(entry['artist'])
            ),
            'original': lambda entry: (
                entry['playlist_order'],
                entry['track_order'],
                normalized(entry['title'])
            )
        }

        return sorted(tracks, key=sorters.get(sort_mode, sorters['title']))

    def on_search(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Input", "Please enter a song name")
            return
        
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first")
            return

        filtered_results = self._find_matching_tracks(query)
        self.show_search_results_display(query, filtered_results)

    def show_search_results_display(self, query, filtered_results):
        sorted_results = sorted(
            filtered_results.values(),
            key=lambda entry: entry['track'].get('title', '').lower()
        )

        def build_search_display(parent):
            self.current_display_view = 'search'
            self._active_combined_refresh = None
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(1, weight=1)

            header_frame = ttk.Frame(parent)
            header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
            header_frame.columnconfigure(0, weight=1)

            results_label = ttk.Label(header_frame, text=f"Search Results: {query}", font=("Helvetica", 15, "bold"))
            results_label.grid(row=0, column=0, sticky=tk.W)

            display_find_var = tk.StringVar()
            find_frame = ttk.Frame(header_frame)
            find_frame.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
            find_label, find_entry = self._create_display_find_controls(find_frame, display_find_var)
            find_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
            find_entry.grid(row=0, column=1, sticky=tk.W)

            results_text = tk.Text(parent, height=18, width=90, state=tk.NORMAL)
            results_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            results_text.tag_configure("display_find_match", background="#fff2a8")

            if not sorted_results:
                results_text.insert(tk.END, f"No songs matching '{query}' were found in your saved playlists.\n\nTry a different query or add more playlists.")
            else:
                for i, entry in enumerate(sorted_results, 1):
                    track = entry['track']
                    in_playlists = sorted(entry['playlists'])
                    title = track.get('title', 'Unknown')
                    artist = track.get('artist', 'Unknown')

                    result_str = f"{i}. {title} by {artist}\n   Found in: {', '.join(in_playlists)}\n\n"
                    results_text.insert(tk.END, result_str)

            results_text.config(state=tk.DISABLED)

            def refresh_find_matches(*_):
                results_text.tag_remove("display_find_match", "1.0", tk.END)
                find_text = display_find_var.get().strip()
                if not find_text:
                    return

                start_index = "1.0"
                first_match = None
                while True:
                    match_index = results_text.search(find_text, start_index, tk.END, nocase=True)
                    if not match_index:
                        break
                    match_end = f"{match_index}+{len(find_text)}c"
                    results_text.tag_add("display_find_match", match_index, match_end)
                    if first_match is None:
                        first_match = match_index
                    start_index = match_end

                if first_match:
                    results_text.see(first_match)

            display_find_var.trace_add("write", refresh_find_matches)

        self._show_display("Search Results", build_search_display)
    
    def open_playlist_window(self):
        PlaylistURLWindow(self.root, self.ytmusic, self.saved_playlists, self)

    def open_spotify_playlist_window(self):
        if not self.spotapi_available:
            messagebox.showerror(
                "Spotify Not Available",
                "Spotify support is disabled because the spotapi package is not installed.\n\nInstall it with: pip install spotapi"
            )
            return
        PlaylistURLWindow(self.root, self.ytmusic, self.saved_playlists, self, source='spotify')

    def view_saved_playlists(self):
        """Show a window with saved playlists"""
        if not self.saved_playlists:
            messagebox.showinfo("Saved Playlists", "No playlists saved yet.\n\nAdd some playlists using the add playlist button.")
            return

        self.show_saved_playlists_display()

    def show_saved_playlists_display(self):
        self._show_display("Saved Playlists", self._build_saved_playlists_display)

    def _build_saved_playlists_display(self, parent):
        self.current_display_view = 'playlists'
        self._active_combined_refresh = None

        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)

        title = ttk.Label(header_frame, text=f"Saved Playlists ({len(self.saved_playlists)})", font=("Helvetica", 15, "bold"))
        title.grid(row=0, column=0, sticky=tk.W)

        display_find_var = tk.StringVar()
        find_frame = ttk.Frame(header_frame)
        find_frame.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        find_label, find_entry = self._create_display_find_controls(find_frame, display_find_var)
        find_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        find_entry.grid(row=0, column=1, sticky=tk.W)

        playlist_by_item = {}

        def selected_playlist_key():
            selected_items = playlists_tree.selection()
            if not selected_items:
                messagebox.showinfo("No Selection", "Select a saved playlist first.")
                return None
            return playlist_by_item.get(selected_items[0])

        def show_selected_playlist_details():
            playlist_key = selected_playlist_key()
            if playlist_key:
                self.show_playlist_details_window(playlist_key)

        details_button = ttk.Button(header_frame, text="Details", command=show_selected_playlist_details)
        details_button.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(8, 0))

        if self._show_youtube_queue_actions():
            def play_selected_playlist_queue():
                playlist_key = selected_playlist_key()
                if playlist_key:
                    self._play_playlist_youtube_queue(playlist_key)

            play_queue_button = ttk.Button(header_frame, text="Play YouTube Queue", command=play_selected_playlist_queue)
            play_queue_button.grid(row=1, column=2, sticky=tk.W, padx=(8, 0), pady=(8, 0))

        table_frame = ttk.Frame(parent)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        playlists_tree = ttk.Treeview(
            table_frame,
            columns=('name', 'source', 'songs', 'tracks', 'id'),
            show='tree headings',
            style="SourceLogo.Treeview",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )
        playlists_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        y_scrollbar.config(command=playlists_tree.yview)
        x_scrollbar.config(command=playlists_tree.xview)

        playlists_tree.heading('#0', text='')
        playlists_tree.heading('name', text='Playlist')
        playlists_tree.heading('source', text='Source')
        playlists_tree.heading('songs', text='Songs')
        playlists_tree.heading('tracks', text='Cached Tracks')
        playlists_tree.heading('id', text='ID')

        playlists_tree.column('#0', width=38, minwidth=38, stretch=False, anchor=tk.CENTER)
        playlists_tree.column('name', width=260, minwidth=160, stretch=False)
        playlists_tree.column('source', width=120, minwidth=90, stretch=False)
        playlists_tree.column('songs', width=80, minwidth=70, stretch=False, anchor=tk.CENTER)
        playlists_tree.column('tracks', width=110, minwidth=90, stretch=False, anchor=tk.CENTER)
        playlists_tree.column('id', width=260, minwidth=160, stretch=False)

        playlist_rows = []
        for playlist_key, pl_data in self._sorted_playlist_items():
            source = pl_data.get('source', 'youtube')
            videos = pl_data.get('videos', set())
            tracks = pl_data.get('tracks', [])
            row_values = (
                pl_data.get('name', 'Unnamed'),
                self._source_name(source),
                len(videos),
                len(tracks),
                pl_data.get('id', playlist_key)
            )
            playlist_rows.append((playlist_key, source, row_values))

        def refresh_playlist_rows(*_):
            playlist_by_item.clear()
            for item_id in playlists_tree.get_children():
                playlists_tree.delete(item_id)

            visible_rows = [
                row
                for row in playlist_rows
                if self._matches_find_query(row[2], display_find_var.get())
            ]

            if not visible_rows:
                playlists_tree.insert(
                    '',
                    tk.END,
                    values=('No saved playlists match the current find text.', '', '', '', '')
                )
                return

            for playlist_key, source, row_values in visible_rows:
                item_id = playlists_tree.insert(
                    '',
                    tk.END,
                    image=self._source_logo_image(source),
                    values=row_values
                )
                playlist_by_item[item_id] = playlist_key

        playlists_tree.bind("<Double-1>", lambda _event: show_selected_playlist_details())
        display_find_var.trace_add("write", refresh_playlist_rows)
        refresh_playlist_rows()

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

    def open_combined_songs_selector(self):
        """Show a combined song view for the selected playlists."""
        if not self.saved_playlists:
            messagebox.showinfo("Combined Songs", "No playlists saved yet.\n\nAdd some playlists using the add playlist button.")
            return

        selected_keys = self._selected_sidebar_playlist_keys()
        if not selected_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist.")
            return

        self.show_combined_songs_display(selected_keys, live=not self.use_display_windows_var.get())

    def show_playlist_selection_display(self, selected_keys=None):
        self.current_display_view = 'playlist_selection'
        self._active_combined_refresh = None
        if selected_keys is None:
            selected_keys = set(self._selected_playlist_keys_from_active_display())

        self._clear_display_frame()

        header_frame = ttk.Frame(self.display_frame)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)

        title = ttk.Label(header_frame, text="Selected Playlists", font=("Helvetica", 15, "bold"))
        title.grid(row=0, column=0, sticky=tk.W)

        settings_button = ttk.Button(header_frame, text="Settings", command=self.show_settings_display)
        settings_button.grid(row=0, column=1, sticky=tk.E)

        selector_frame = ttk.LabelFrame(self.display_frame, text="Playlists", padding=(8, 6))
        selector_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.display_playlist_vars = self._build_playlist_checkbox_selector(
            selector_frame,
            selected_keys=selected_keys
        )

        action_frame = ttk.Frame(self.display_frame)
        action_frame.grid(row=2, column=0, sticky=tk.E, pady=(8, 0))

        select_all_button = ttk.Button(
            action_frame,
            text="Select All",
            command=lambda: self._set_playlist_selection(self.display_playlist_vars, True)
        )
        select_all_button.grid(row=0, column=0, padx=5)

        clear_button = ttk.Button(
            action_frame,
            text="Clear",
            command=lambda: self._set_playlist_selection(self.display_playlist_vars, False)
        )
        clear_button.grid(row=0, column=1, padx=5)

        self.display_frame.columnconfigure(0, weight=1)
        self.display_frame.rowconfigure(1, weight=1)

    def show_combined_songs_display(self, playlist_keys, live=False):
        playlist_count = len(playlist_keys)

        def build_combined_display(parent):
            self.current_display_view = 'combined'
            self._active_combined_refresh = None
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(1, weight=1)

            header_frame = ttk.Frame(parent)
            header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            header_frame.columnconfigure(4, weight=1)

            title_text = "Combined Songs" if live else f"Combined Songs ({playlist_count} playlists)"
            title = ttk.Label(header_frame, text=title_text, font=("Helvetica", 15, "bold"))
            title.grid(row=0, column=0, sticky=tk.W)

            results_frame = ttk.Frame(parent)
            results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            results_playlist_keys = self._selected_sidebar_playlist_keys if live else playlist_keys
            self._build_combined_songs_results(results_frame, results_playlist_keys, live=live)

        self._show_display("Combined Songs", build_combined_display, geometry="1080x620")

    def _set_playlist_selection(self, playlist_vars, selected):
        for _, selected_var in playlist_vars:
            selected_var.set(selected)
        self._refresh_live_combined_if_active()

    def _selected_playlist_keys(self, playlist_vars):
        return [playlist_key for playlist_key, selected_var in playlist_vars if selected_var.get()]

    def _build_playlist_checkbox_selector(self, parent, on_change=None, selected_keys=None):
        list_frame = ttk.Frame(parent)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        canvas = tk.Canvas(list_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        checkbox_frame = ttk.Frame(canvas)

        checkbox_window = canvas.create_window((0, 0), window=checkbox_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_checkbox_width(event):
            canvas.itemconfigure(checkbox_window, width=event.width)

        def on_mousewheel(event):
            if getattr(event, 'num', None) == 4:
                scroll_units = -3
            elif getattr(event, 'num', None) == 5:
                scroll_units = 3
            elif event.delta:
                scroll_units = -1 if event.delta > 0 else 1
            else:
                scroll_units = 0

            if scroll_units:
                canvas.yview_scroll(scroll_units, "units")
            return "break"

        def bind_mousewheel(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)

        # Bind both the canvas and row widgets so scrolling works over the whole list area.
        checkbox_frame.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", update_checkbox_width)
        for widget in (list_frame, canvas, checkbox_frame):
            bind_mousewheel(widget)

        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        playlist_vars = []
        for row_index, (playlist_key, pl_data) in enumerate(self._sorted_playlist_items()):
            source = pl_data.get('source', 'youtube')
            playlist_name = pl_data.get('name', f'Playlist {playlist_key}')
            song_count = len(pl_data.get('tracks') or pl_data.get('videos', set()))
            selected_var = tk.BooleanVar(value=selected_keys is None or playlist_key in selected_keys)
            playlist_vars.append((playlist_key, selected_var))

            row_frame = ttk.Frame(checkbox_frame, padding=(0, 1))
            row_frame.grid(row=row_index, column=0, sticky=(tk.W, tk.E))
            checkbox_frame.columnconfigure(0, weight=1)
            row_frame.columnconfigure(1, weight=1)

            badge = self._create_source_badge(row_frame, source)
            badge.grid(row=0, column=0, padx=(0, 5), sticky=tk.W)

            checkbutton = ttk.Checkbutton(
                row_frame,
                text=f"{playlist_name} ({song_count} songs)",
                variable=selected_var,
                command=on_change
            )
            checkbutton.grid(row=0, column=1, sticky=tk.W)
            for widget in (row_frame, badge, checkbutton):
                bind_mousewheel(widget)

        return playlist_vars

    def _build_combined_songs_results(self, parent, playlist_keys, live=False):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        toolbar_frame.columnconfigure(5, weight=1)

        sort_label = ttk.Label(toolbar_frame, text="Sort by:")
        sort_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=(0, 6))

        sort_var = tk.StringVar(value='Title (A-Z)')
        sort_combo = ttk.Combobox(
            toolbar_frame,
            textvariable=sort_var,
            values=list(self.COMBINED_SORT_OPTIONS.keys()),
            state='readonly',
            width=24
        )
        sort_combo.grid(row=0, column=1, sticky=tk.W, pady=(0, 6))

        display_find_var = tk.StringVar()
        find_label, find_entry = self._create_display_find_controls(toolbar_frame, display_find_var)
        find_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 6))
        find_entry.grid(row=1, column=1, sticky=(tk.W, tk.E))

        count_var = tk.StringVar(value="")
        count_label = ttk.Label(toolbar_frame, textvariable=count_var)
        count_label.grid(row=0, column=5, sticky=tk.E, pady=(0, 6))

        table_frame = ttk.Frame(parent)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        show_queue_metadata = self._show_youtube_queue_actions()
        song_columns = ('title', 'artist', 'playback', 'playlists') if show_queue_metadata else ('title', 'artist', 'playlists')

        songs_tree = ttk.Treeview(
            table_frame,
            columns=song_columns,
            show='tree headings',
            style="SourceLogo.Treeview",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )
        songs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        y_scrollbar.config(command=songs_tree.yview)
        x_scrollbar.config(command=songs_tree.xview)

        songs_tree.heading('#0', text='')
        songs_tree.heading('title', text='Title')
        songs_tree.heading('artist', text='Artist')
        if show_queue_metadata:
            songs_tree.heading('playback', text='Playback')
        songs_tree.heading('playlists', text='Playlists')

        songs_tree.column('#0', width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
        songs_tree.column('title', width=260, minwidth=160, stretch=False)
        songs_tree.column('artist', width=190, minwidth=120, stretch=False)
        if show_queue_metadata:
            songs_tree.column('playback', width=110, minwidth=90, stretch=False, anchor=tk.CENTER)
            songs_tree.column('playlists', width=560, minwidth=220, stretch=False)
        else:
            songs_tree.column('playlists', width=670, minwidth=260, stretch=False)

        entry_by_item = {}
        visible_entries = []

        # Button commands read this list so queued playback follows the current sort/find view.
        details_button = ttk.Button(
            toolbar_frame,
            text="Details",
            command=lambda: self._show_selected_entry_details(songs_tree, entry_by_item)
        )
        details_button.grid(row=1, column=2, sticky=tk.W, padx=(10, 4))

        play_button = ttk.Button(
            toolbar_frame,
            text="Play",
            command=lambda: self._play_selected_tree_entry(songs_tree, entry_by_item)
        )
        play_button.grid(row=1, column=3, sticky=tk.W, padx=4)

        if self._show_youtube_queue_actions():
            play_queue_button = ttk.Button(
                toolbar_frame,
                text="Play YouTube Queue",
                command=lambda: self._play_entries_as_youtube_queue(visible_entries, "Combined Songs")
            )
            play_queue_button.grid(row=1, column=4, sticky=tk.W, padx=(4, 0))

        def refresh_results(*_):
            nonlocal visible_entries
            selected_playlist_keys = playlist_keys() if callable(playlist_keys) else playlist_keys
            entries = self._collect_combined_tracks(selected_playlist_keys, merge_duplicates=True)
            entries = self._sort_combined_tracks(entries, sort_var.get())
            filtered_entries = [
                entry
                for entry in entries
                if self._matches_find_query(
                    [
                        entry['title'],
                        entry['artist'],
                        self._format_playlist_occurrences(entry, limit=None),
                        ', '.join(sorted(self._source_name(source) for source in entry['sources']))
                    ] + ([self._entry_queue_status(entry)] if show_queue_metadata else []),
                    display_find_var.get()
                )
            ]
            visible_entries = filtered_entries

            entry_by_item.clear()
            for item_id in songs_tree.get_children():
                songs_tree.delete(item_id)

            if not filtered_entries:
                message = 'No songs found for the selected playlists.'
                if entries:
                    message = 'No songs match the current find text.'
                songs_tree.insert(
                    '',
                    tk.END,
                    values=(message, '', '', '') if show_queue_metadata else (message, '', '')
                )
            else:
                for entry in filtered_entries:
                    playlist_text = self._format_playlist_occurrences(entry, self.PLAYLIST_DISPLAY_LIMIT)
                    row_values = (
                        (entry['title'], entry['artist'], self._entry_queue_status(entry), playlist_text)
                        if show_queue_metadata
                        else (entry['title'], entry['artist'], playlist_text)
                    )
                    item_id = songs_tree.insert(
                        '',
                        tk.END,
                        image=self._source_logo_for_sources(entry['sources']),
                        values=row_values
                    )
                    entry_by_item[item_id] = entry

            if display_find_var.get().strip() and len(filtered_entries) != len(entries):
                count_var.set(f"{len(filtered_entries)} of {len(entries)} songs")
            else:
                count_var.set(f"{len(entries)} songs")

        sort_combo.bind("<<ComboboxSelected>>", refresh_results)
        songs_tree.bind("<Double-1>", lambda _event: self._show_selected_entry_details(songs_tree, entry_by_item))
        display_find_var.trace_add("write", refresh_results)
        if live:
            self._active_combined_refresh = refresh_results

        refresh_results()

    def _find_duplicate_entries(self, playlist_keys):
        combined_entries = self._collect_combined_tracks(playlist_keys, merge_duplicates=True)
        return [
            entry
            for entry in combined_entries
            if entry['appearance_count'] > 1
        ]

    def show_duplicate_songs_display(self, duplicate_entries, selected_count):
        duplicate_entries = sorted(
            duplicate_entries,
            key=lambda entry: (-entry['appearance_count'], entry['title'].lower(), entry['artist'].lower())
        )

        def build_duplicate_display(parent):
            self.current_display_view = 'duplicates'
            self._active_combined_refresh = None
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(1, weight=1)

            header_frame = ttk.Frame(parent)
            header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            header_frame.columnconfigure(0, weight=1)

            title_var = tk.StringVar()
            title = ttk.Label(header_frame, textvariable=title_var, font=("Helvetica", 15, "bold"))
            title.grid(row=0, column=0, sticky=tk.W)

            display_find_var = tk.StringVar()
            find_frame = ttk.Frame(header_frame)
            find_frame.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
            find_label, find_entry = self._create_display_find_controls(find_frame, display_find_var)
            find_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
            find_entry.grid(row=0, column=1, sticky=tk.W)

            table_frame = ttk.Frame(parent)
            table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
            y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
            x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

            show_queue_metadata = self._show_youtube_queue_actions()
            duplicate_columns = ('title', 'artist', 'playback', 'playlists') if show_queue_metadata else ('title', 'artist', 'playlists')

            duplicates_tree = ttk.Treeview(
                table_frame,
                columns=duplicate_columns,
                show='tree headings',
                style="SourceLogo.Treeview",
                yscrollcommand=y_scrollbar.set,
                xscrollcommand=x_scrollbar.set
            )
            duplicates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            y_scrollbar.config(command=duplicates_tree.yview)
            x_scrollbar.config(command=duplicates_tree.xview)

            duplicates_tree.heading('#0', text='')
            duplicates_tree.heading('title', text='Title')
            duplicates_tree.heading('artist', text='Artist')
            if show_queue_metadata:
                duplicates_tree.heading('playback', text='Playback')
            duplicates_tree.heading('playlists', text='Playlists')

            duplicates_tree.column('#0', width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
            duplicates_tree.column('title', width=260, minwidth=160, stretch=False)
            duplicates_tree.column('artist', width=190, minwidth=120, stretch=False)
            if show_queue_metadata:
                duplicates_tree.column('playback', width=110, minwidth=90, stretch=False, anchor=tk.CENTER)
                duplicates_tree.column('playlists', width=560, minwidth=220, stretch=False)
            else:
                duplicates_tree.column('playlists', width=670, minwidth=260, stretch=False)

            entry_by_item = {}
            visible_entries = []

            # Queue playback intentionally uses the filtered duplicate rows currently on screen.
            details_button = ttk.Button(
                header_frame,
                text="Details",
                command=lambda: self._show_selected_entry_details(duplicates_tree, entry_by_item)
            )
            details_button.grid(row=1, column=1, sticky=tk.W, padx=(10, 4), pady=(8, 0))

            play_button = ttk.Button(
                header_frame,
                text="Play",
                command=lambda: self._play_selected_tree_entry(duplicates_tree, entry_by_item)
            )
            play_button.grid(row=1, column=2, sticky=tk.W, padx=4, pady=(8, 0))

            if self._show_youtube_queue_actions():
                play_queue_button = ttk.Button(
                    header_frame,
                    text="Play YouTube Queue",
                    command=lambda: self._play_entries_as_youtube_queue(visible_entries, "Selected Playlist Duplicates")
                )
                play_queue_button.grid(row=1, column=3, sticky=tk.W, padx=4, pady=(8, 0))

            def refresh_duplicate_rows(*_):
                nonlocal visible_entries
                entry_by_item.clear()
                for item_id in duplicates_tree.get_children():
                    duplicates_tree.delete(item_id)

                visible_entries = [
                    entry
                    for entry in duplicate_entries
                    if self._matches_find_query(
                        [
                            entry['title'],
                            entry['artist'],
                            self._format_playlist_occurrences(entry, limit=None),
                            ', '.join(sorted(self._source_name(source) for source in entry['sources']))
                        ] + ([self._entry_queue_status(entry)] if show_queue_metadata else []),
                        display_find_var.get()
                    )
                ]

                if display_find_var.get().strip() and len(visible_entries) != len(duplicate_entries):
                    title_var.set(f"Selected Playlist Duplicates ({len(visible_entries)} of {len(duplicate_entries)} shown)")
                else:
                    title_var.set(f"Selected Playlist Duplicates ({len(duplicate_entries)} found)")

                if not visible_entries:
                    message = f"No duplicates found in {selected_count} selected playlist."
                    if selected_count != 1:
                        message = f"No duplicates found in {selected_count} selected playlists."
                    if duplicate_entries:
                        message = "No duplicate songs match the current find text."
                    duplicates_tree.insert(
                        '',
                        tk.END,
                        values=(message, '', '', '') if show_queue_metadata else (message, '', '')
                    )
                    return

                for entry in visible_entries:
                    playlist_text = self._format_playlist_occurrences(entry, self.PLAYLIST_DISPLAY_LIMIT)
                    row_values = (
                        (entry['title'], entry['artist'], self._entry_queue_status(entry), playlist_text)
                        if show_queue_metadata
                        else (entry['title'], entry['artist'], playlist_text)
                    )
                    item_id = duplicates_tree.insert(
                        '',
                        tk.END,
                        image=self._source_logo_for_sources(entry['sources']),
                        values=row_values
                    )
                    entry_by_item[item_id] = entry

            duplicates_tree.bind("<Double-1>", lambda _event: self._show_selected_entry_details(duplicates_tree, entry_by_item))
            display_find_var.trace_add("write", refresh_duplicate_rows)
            refresh_duplicate_rows()

        self._show_display("Selected Playlist Duplicates", build_duplicate_display, geometry="1080x620")
    
    def find_duplicate_songs(self):
        """Find and display songs that appear multiple times in selected playlists"""
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first")
            return

        selected_playlist_keys = self._selected_sidebar_playlist_keys()
        if not selected_playlist_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist.")
            return

        try:
            duplicates = self._find_duplicate_entries(selected_playlist_keys)
            self.show_duplicate_songs_display(duplicates, len(selected_playlist_keys))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to find duplicates: {e}")
    
    def update_selected_playlists(self):
        """Update selected saved playlists with latest data from their source"""
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "You have no saved playlists to update.")
            return

        selected_playlist_keys = self._selected_sidebar_playlist_keys()
        if not selected_playlist_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist to update.")
            return

        try:
            updated_count = 0
            failed_playlists = []
            cancelled = {'value': False}
            
            # Create a progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Updating Playlists")
            progress_window.geometry("400x150")
            progress_window.resizable(False, False)
            self._configure_window_icon(progress_window)
            
            main_frame = ttk.Frame(progress_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Title
            title = ttk.Label(main_frame, text="Updating Selected Playlists", font=("Helvetica", 12, "bold"))
            title.grid(row=0, column=0, columnspan=2, pady=10)
            
            # Status label
            status_label = ttk.Label(main_frame, text="")
            status_label.grid(row=1, column=0, columnspan=2, pady=10)
            
            # Progress bar
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100, length=300)
            progress_bar.grid(row=2, column=0, columnspan=2, pady=10)

            def cancel_update():
                cancelled['value'] = True
                status_label.config(text="Cancelling after current playlist...")

            # Cancel button
            cancel_button = ttk.Button(main_frame, text="Cancel", command=cancel_update)
            cancel_button.grid(row=3, column=0, columnspan=2, pady=10)
            progress_window.protocol("WM_DELETE_WINDOW", cancel_update)
            
            progress_window.update()
            
            total_playlists = len(selected_playlist_keys)
            
            for idx, playlist_key in enumerate(selected_playlist_keys):
                if cancelled['value']:
                    break

                try:
                    pl_data = self.saved_playlists.get(playlist_key)
                    if not pl_data:
                        continue

                    pl_name = pl_data.get('name', f'Playlist {playlist_key}')
                    status_label.config(text=f"Updating: {pl_name}...")
                    progress_var.set((idx / total_playlists) * 100)
                    progress_window.update()

                    source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
                    if source == 'youtube':
                        self.saved_playlists[playlist_key] = self._fetch_youtube_playlist_entry(playlist_id, pl_name)
                    elif source == 'spotify':
                        self.saved_playlists[playlist_key] = self._fetch_spotify_playlist_entry(playlist_id, pl_name)
                    else:
                        raise RuntimeError(f"Unsupported playlist source: {source}")

                    updated_count += 1
                    
                except Exception as e:
                    print(f"Error updating playlist {playlist_key}: {e}")
                    failed_playlists.append(pl_name)
            
            # Save updated playlists
            self.save_playlists()
            self.refresh_playlist_selectors(selected_keys=set(selected_playlist_keys))
            self._refresh_live_combined_if_active()
            
            # Update progress bar to 100%
            progress_var.set(100)
            progress_window.update()
            
            # Close progress window
            progress_window.destroy()
            
            # Show results
            if cancelled['value']:
                message = f"Updated {updated_count} of {total_playlists} selected playlists before cancelling."
                if failed_playlists:
                    message += "\n\nFailed to update:\n" + "\n".join(failed_playlists)
                messagebox.showinfo("Update Cancelled", message)
            elif failed_playlists:
                message = f"Updated {updated_count} of {total_playlists} selected playlists.\n\nFailed to update:\n" + "\n".join(failed_playlists)
                messagebox.showwarning("Update Complete", message)
            else:
                messagebox.showinfo("Success", f"Successfully updated {updated_count} selected playlists!")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update playlists: {e}")
