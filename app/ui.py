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
from tkinter import ttk, messagebox
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.exceptions import BadOAuthClient

from app.app_info import APP_NAME, APP_VERSION
from app.app_paths import resource_path, user_data_path
from app.app_settings import AppSettings, AUTO_DELETE_TEMP_ON_EXIT, USE_DISPLAY_WINDOWS
from app.views.playlist_url_window import PlaylistURLWindow
from app.views import combined_songs_view
from app.views import duplicates_view
from app.services.playlist_library import PlaylistLibrary
from app.services.queue_service import QueueService
from app.views import playlist_checkbox_selector
from app.views import playlist_selection_view
from app.services import playlist_store
from app.views import search_results_view
from app.views import saved_playlists_view
from app.views import settings_view
from app.views import temporary_playlists_view
from app.views import youtube_music_auth_views
from app.services import text_utils
from app.services.update_checker import UpdateChecker
from app.services.youtube_music_account import YouTubeMusicAccount

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
    YOUTUBE_QUEUE_ACTIONS_ENV_VAR = "PLAYLIST_MANAGER_SHOW_QUEUE_ACTIONS"
    DISABLE_UPDATE_CHECK_ENV_VAR = "PLAYLIST_MANAGER_DISABLE_UPDATE_CHECK"
    # Opt-in toggle for the (failed) rotating-cookie-stripping experiment; off by default so it
    # is not tied to the debug build. See _build_browser_authenticated_ytmusic.
    STRIP_ROTATING_COOKIES_ENV_VAR = "PLAYLIST_MANAGER_STRIP_ROTATING_COOKIES"
    PLAYLIST_DISPLAY_LIMIT = 140
    YOUTUBE_TEMP_PLAYLIST_CHUNK_SIZE = 50
    SOURCE_LABELS = playlist_store.SOURCE_LABELS
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
        
        # The saved-playlists state + persistence live in the PlaylistLibrary service; the
        # controller reaches the dict through the saved_playlists property below. Per-entry
        # normalization/serialization/ordering are injected (they need network/source access).
        self.library = PlaylistLibrary(
            self.PLAYLIST_FILE,
            normalize_entry=self._normalize_playlist_entry,
            serialize_entry=self._serialize_playlist_entry,
            sort_key=self._playlist_sort_key,
        )

        # Load saved playlists on startup
        self.load_playlists()
        
        # Show loaded playlists count
        if self.saved_playlists:
            print(f"Loaded {len(self.saved_playlists)} saved playlists")
            # Could add a status label here if desired

        self.app_settings = AppSettings()
        self.use_display_windows_var = tk.BooleanVar(
            value=self.app_settings.get_bool(USE_DISPLAY_WINDOWS, False)
        )
        self.auto_delete_temp_on_exit_var = tk.BooleanVar(
            value=self.app_settings.get_bool(AUTO_DELETE_TEMP_ON_EXIT, False)
        )
        self._closing = False
        self.app_icon_image = self._load_app_icon_image()
        self.source_logo_images = self._build_source_logo_images()
        self.sidebar_playlist_vars = []
        self.display_playlist_vars = []
        self.active_find_entry = None
        self.current_display_view = 'empty'
        self.update_checker = UpdateChecker()
        self.youtube_account = YouTubeMusicAccount(opener=self._open_external_url)
        self.queue_service = QueueService(self.youtube_account, self.YOUTUBE_TEMP_PLAYLIST_CHUNK_SIZE)
        self.youtube_queue_auth_error = None
        self.youtube_queue_headers_verified = False
        self.authenticated_ytmusic = self._build_authenticated_ytmusic()
        self.browser_authenticated_ytmusic = self._build_browser_authenticated_ytmusic()
        self._configure_window_icon(self.root)
        self.style = ttk.Style()
        self._configure_button_feedback()
        self.style.configure("SourceLogo.Treeview", rowheight=32)
        self._enable_global_label_wrap()
        self._configure_table_styles()
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

        # Keep the Search button directly beside the search field so the pairing is obvious.
        search_row = ttk.Frame(self.sidebar_frame)
        search_row.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        search_row.columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(search_row)
        self.search_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        self.root.bind_all("<Control-f>", self._focus_active_find_or_sidebar)
        self.root.bind_all("<Command-f>", self._focus_active_find_or_sidebar)

        search_button = ttk.Button(search_row, text="Search", command=self.on_search)
        search_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(6, 0))

        button_frame = ttk.Frame(self.sidebar_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        button_frame.columnconfigure(0, weight=1)

        # "View Songs" is the primary action and the default landing view: it shows the
        # combined songs of the selected playlists. Styled and placed to stand out.
        combined_songs_button = ttk.Button(button_frame, text="View Songs", style="Primary.TButton", command=self.open_combined_songs_selector)
        combined_songs_button.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(2, 8))

        add_playlist_button = ttk.Button(button_frame, text="Add Playlist", command=self.open_playlist_window)
        add_playlist_button.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)

        view_playlists_button = ttk.Button(button_frame, text="View Saved Playlists", command=self.view_saved_playlists)
        view_playlists_button.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)

        find_duplicates_button = ttk.Button(button_frame, text="Find Duplicates in Selection", command=self.find_duplicate_songs)
        find_duplicates_button.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=2)

        update_selected_button = ttk.Button(button_frame, text="Update Selected Playlists", command=self.update_selected_playlists)
        update_selected_button.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=2)

        # "Play in YouTube Music" creates a private temporary playlist from the selected
        # playlists and opens it on music.youtube.com. The first use prompts to set up queue
        # headers; that one-time setup lives in Settings > Set Queue Headers, not here.
        play_youtube_music_button = ttk.Button(button_frame, text="Play in YouTube Music", command=self.play_selection_in_youtube_music)
        play_youtube_music_button.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=2)

        settings_button = ttk.Button(button_frame, text="Settings", command=self.show_settings_display)
        settings_button.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=(12, 2))

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
        if self.use_display_windows_var.get():
            # Separate-windows mode persisted on: set up that layout (sidebar selector hidden,
            # the playlist picker in the main area) instead of the inline combined landing.
            self._on_display_mode_changed()
        else:
            # Land on the primary "View Songs" view; it tracks the sidebar selection live.
            self.show_combined_songs_display([], live=True)
        self._schedule_initial_update_check()
        self._schedule_temporary_playlist_cleanup_prompt()

    def _on_close(self):
        if self._closing:
            return

        records = self.youtube_account.load_temporary_playlists()
        if not records:
            self._finalize_close()
            return

        if self.auto_delete_temp_on_exit_var.get():
            self._closing = True
            self._delete_temporary_playlists_then_close(records)
            return

        choice = self._ask_delete_temporary_on_exit(records)
        if choice == "cancel":
            return
        if choice == "delete":
            self._closing = True
            self._delete_temporary_playlists_then_close(records)
        else:
            self._finalize_close()

    def _finalize_close(self):
        self.root.destroy()

    def _ask_delete_temporary_on_exit(self, records):
        """Modal exit prompt. Returns 'delete', 'keep', or 'cancel'. A checkbox
        lets the user opt into always deleting on exit without being asked again."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Temporary YouTube Music Playlists")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        self._configure_window_icon(dialog)

        frame = ttk.Frame(dialog, padding="18")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        frame.columnconfigure(0, weight=1)

        count = len(records)
        message = ttk.Label(
            frame,
            text=(
                f"{count} temporary YouTube Music playlist{'' if count == 1 else 's'} "
                f"{'is' if count == 1 else 'are'} still on your account.\n\n"
                "Delete them now so they don't pile up?"
            ),
            wraplength=420,
            justify=tk.LEFT,
        )
        message.grid(row=0, column=0, sticky=tk.W)

        always_var = tk.BooleanVar(value=False)
        always_check = ttk.Checkbutton(
            frame,
            text="Always delete temporary playlists when I close the app",
            variable=always_var,
        )
        always_check.grid(row=1, column=0, sticky=tk.W, pady=(12, 0))

        result = {"choice": "cancel"}

        def choose(value):
            # The checkbox means "always delete from now on", so it only takes
            # effect alongside the delete action.
            if value == "delete" and always_var.get():
                self.auto_delete_temp_on_exit_var.set(True)
                self.app_settings.set(AUTO_DELETE_TEMP_ON_EXIT, True)
            result["choice"] = value
            dialog.destroy()

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, sticky=tk.E, pady=(16, 0))

        cancel_button = ttk.Button(button_row, text="Cancel", command=lambda: choose("cancel"))
        cancel_button.grid(row=0, column=0, padx=(0, 6))
        keep_button = ttk.Button(button_row, text="Keep and Close", command=lambda: choose("keep"))
        keep_button.grid(row=0, column=1, padx=(0, 6))
        delete_button = ttk.Button(button_row, text="Delete and Close", command=lambda: choose("delete"))
        delete_button.grid(row=0, column=2)

        dialog.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
        dialog.grab_set()
        delete_button.focus_set()
        self.root.wait_window(dialog)
        return result["choice"]

    def _delete_temporary_playlists_then_close(self, records):
        client = self._youtube_music_queue_client()
        if client is None:
            messagebox.showwarning(
                "Temporary Playlists",
                "Couldn't delete the temporary playlists because the YouTube Music queue "
                "headers are missing or expired. They remain on your account — delete them "
                "next time from Settings > Temporary Playlists.",
            )
            self._finalize_close()
            return

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Deleting Temporary Playlists")
        progress_window.geometry("430x150")
        progress_window.resizable(False, False)
        progress_window.protocol("WM_DELETE_WINDOW", lambda: None)
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

        state = {"finished": False}

        def finalize_once():
            if state["finished"]:
                return
            state["finished"] = True
            if progress_window.winfo_exists():
                progress_window.destroy()
            self._finalize_close()

        def worker():
            deleted_ids = []
            for index, record in enumerate(records, start=1):
                with contextlib.suppress(Exception):
                    self.root.after(
                        0,
                        lambda record=record, index=index: status_var.set(
                            f"Deleting {index} of {len(records)}: {record.title}"
                        ),
                    )
                try:
                    response = client.delete_playlist(record.playlist_id)
                    if isinstance(response, dict) and "status" in response and "SUCCEEDED" not in response["status"]:
                        raise RuntimeError(response)
                    deleted_ids.append(record.playlist_id)
                except Exception:
                    continue

            if deleted_ids:
                with contextlib.suppress(Exception):
                    self.youtube_account.forget_temporary_playlists(deleted_ids)

            with contextlib.suppress(Exception):
                self.root.after(0, finalize_once)

        threading.Thread(target=worker, daemon=True).start()
        # Safety valve: never trap the user in an un-closable window if the
        # network hangs or YouTube Music stops responding.
        self.root.after(20000, finalize_once)

    def _on_auto_delete_temp_changed(self):
        self.app_settings.set(
            AUTO_DELETE_TEMP_ON_EXIT,
            bool(self.auto_delete_temp_on_exit_var.get()),
        )

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

    def _configure_table_styles(self):
        # Light visual touch-up that works across platforms: bolder table headers and a
        # "Danger" button accent for destructive actions (delete). On macOS's native aqua
        # theme button colors are partly ignored, so this is best-effort, not guaranteed.
        try:
            self.style.configure("Treeview.Heading", font=("Helvetica", 11, "bold"))
            self.style.configure("Danger.TButton", padding=(7, 4))
            self.style.map(
                "Danger.TButton",
                foreground=[
                    ("disabled", "#8a8a8a"),
                    ("pressed", "#7a1414"),
                    ("active", "#a31515"),
                    ("!disabled", "#b3261e"),
                ],
            )
        except tk.TclError:
            pass

    def _enable_global_label_wrap(self):
        """Wrap every text label to its current width so long or dynamic messages can never be
        clipped off-screen. The app lays content out in weight=1 columns, so a label's width is
        container-driven (no shrink-to-fit feedback loop). Image-only labels are skipped; list /
        tree / text widgets are unaffected and keep their own (horizontal) scrolling.
        """
        def wrap_label(event):
            label = event.widget
            try:
                if label.cget("image"):
                    return
            except tk.TclError:
                return
            width = event.width - 2
            if width > 1:
                with contextlib.suppress(tk.TclError):
                    label.configure(wraplength=width)

        for label_class in ("TLabel", "Label"):
            self.root.bind_class(label_class, "<Configure>", wrap_label, add="+")

    def _configure_button_feedback(self):
        try:
            self.style.configure("TButton", padding=(7, 4))
            # Accent style for the primary "View Songs" action so it stands out.
            self.style.configure("Primary.TButton", padding=(7, 8), font=("Helvetica", 12, "bold"))
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

    def _build_browser_authenticated_ytmusic(self):
        if not self.youtube_account.has_browser_auth():
            return None

        # EXPERIMENTAL & OFF BY DEFAULT (opt in via PLAYLIST_MANAGER_STRIP_ROTATING_COOKIES=1).
        # Strips Google's rotating per-session cookies to test whether the saved headers then
        # outlive the ~hourly session rotation. TESTED — it did NOT extend session lifetime, so
        # it is no longer tied to the debug build (debug builds keep working queue auth); kept as
        # a reference implementation. See YouTubeMusicAccount.build_browser_authenticated_client.
        strip_rotating_cookies = os.environ.get(
            self.STRIP_ROTATING_COOKIES_ENV_VAR, ""
        ).lower() in {"1", "true", "yes", "on"}
        if strip_rotating_cookies:
            print("[experiment] Building queue client with rotating session cookies stripped.")

        try:
            return self.youtube_account.build_browser_authenticated_client(
                strip_rotating_cookies=strip_rotating_cookies
            )
        except Exception as e:
            print(f"Could not initialize YouTube Music browser-auth client: {e}")
            return None

    def _youtube_music_queue_client(self):
        if self.browser_authenticated_ytmusic is None:
            self.browser_authenticated_ytmusic = self._build_browser_authenticated_ytmusic()
        return self.browser_authenticated_ytmusic

    def _is_youtube_music_connected(self):
        return self.authenticated_ytmusic is not None or self.youtube_account.is_ready()

    def _is_youtube_music_queue_connected(self):
        return (
            self.youtube_queue_auth_error is None
            and (self.browser_authenticated_ytmusic is not None or self.youtube_account.has_browser_auth())
        )

    def _youtube_music_auth_status(self):
        if self._is_youtube_music_connected():
            return "Connected"
        if self.youtube_account.token_file.exists():
            return "Saved token incomplete, reconnect needed"
        if self.youtube_account.has_client_credentials():
            return "OAuth client saved, sign-in needed"
        return "Not connected"

    def _youtube_music_queue_auth_status(self):
        if self.youtube_queue_auth_error:
            return "Saved browser headers failed, refresh needed"
        if self.youtube_queue_headers_verified:
            return "Browser headers verified"
        if self._is_youtube_music_queue_connected():
            return "Browser headers saved"
        if self.youtube_account.browser_auth_file.exists():
            return "Saved browser headers invalid, refresh needed"
        return "Not configured"

    def _schedule_initial_update_check(self):
        if os.environ.get(self.DISABLE_UPDATE_CHECK_ENV_VAR, "").lower() in {"1", "true", "yes", "on"}:
            return
        self.root.after(1500, lambda: self.check_for_updates(silent=True))

    def _schedule_temporary_playlist_cleanup_prompt(self):
        if not self.youtube_account.load_temporary_playlists():
            return
        # Show this almost immediately (just after the main window paints) so the user has to
        # deal with it before starting to click around — a long delay risks a misclick when the
        # modal suddenly appears. It also lands before the silent update check (1500 ms).
        self.root.after(200, self._handle_startup_temporary_playlists)

    def _handle_startup_temporary_playlists(self):
        records = self.youtube_account.load_temporary_playlists()
        if not records:
            return

        if self.auto_delete_temp_on_exit_var.get():
            # The preference is "always delete on exit"; clean up anything a
            # previous crash left behind, but only if we can actually reach
            # YouTube Music (otherwise leave them for a later manual cleanup).
            if self._is_youtube_music_queue_connected():
                self.delete_temporary_youtube_playlists(prompt=False)
            return

        self._prompt_for_temporary_playlist_cleanup(records)

    def _prompt_for_temporary_playlist_cleanup(self, records=None):
        if records is None:
            records = self.youtube_account.load_temporary_playlists()
        if not records:
            return

        count = len(records)
        should_delete = messagebox.askyesno(
            "Temporary YouTube Music Playlists",
            (
                f"{count} temporary playlist{'' if count == 1 else 's'} from previous queue "
                f"sessions {'is' if count == 1 else 'are'} still on your account.\n\n"
                "Delete them now? You can also review each one — and what it was merged "
                "from — later in Settings > Temporary Playlists."
            ),
            parent=self.root,
            # Default to "No" so an accidental Enter / misclick on the just-appeared modal does
            # not delete playlists; deletion stays a deliberate choice (or later, manual cleanup).
            default=messagebox.NO,
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
    
    @property
    def saved_playlists(self):
        return self.library.playlists

    @saved_playlists.setter
    def saved_playlists(self, value):
        self.library.playlists = value

    def _playlist_sort_key(self, item):
        playlist_key, pl_data = item
        return (
            text_utils.normalize_search_text(pl_data.get('name', '')),
            text_utils.normalize_search_text(self._source_name(pl_data.get('source', 'youtube'))),
            str(playlist_key).lower(),
        )

    def load_playlists(self):
        """Load saved playlists from disk, re-saving if older data needed migrating."""
        if self.library.load():
            print("Migrating playlist data to the current format...")
            self.save_playlists()
            print("Migration complete.")

    # SpotAPI (spotapi.PublicPlaylist) is used for public Spotify playlist access.
    # No client credentials are required for public playlist fetching via SpotAPI.

    def _normalize_playlist_entry(self, stored_key, pl_data):
        if not isinstance(pl_data, dict):
            return None

        source, playlist_id = playlist_store.normalize_playlist_identity(stored_key, pl_data)
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
        source, playlist_id = playlist_store.normalize_playlist_identity(playlist_key, pl_data)
        return {
            'source': source,
            'id': playlist_id,
            'name': pl_data.get('name', 'Unnamed Playlist'),
            'videos': sorted(self._coerce_id_set(pl_data.get('videos'))),
            'tracks': self._normalize_tracks(source, pl_data.get('tracks', []))
        }

    def _delete_saved_playlists(self, playlist_keys):
        """Remove saved playlists from memory + disk and refresh the sidebar selectors.

        Returns the number actually removed.
        """
        removed = self.library.delete(playlist_keys)
        if removed:
            self.save_playlists()
            self.refresh_playlist_selectors()
        return removed

    def save_playlists(self):
        """Persist playlists to disk (the library handles atomic write + backup restore)."""
        try:
            self.library.save()
        except Exception as e:
            print(f"Error saving playlists: {e}")
            messagebox.showerror("Error", f"Failed to save playlists: {e}")
    
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

    def _source_name(self, source):
        return self.SOURCE_LABELS.get(source, source.title() if source else 'Unknown')

    def _sorted_playlist_items(self):
        return self.library.sorted_items()

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

        def on_yscroll(first, last):
            # Auto-hide the scrollbar (and its trough) when everything fits; the canvas column
            # has weight so it reclaims the freed space.
            if float(first) <= 0.0 and float(last) >= 1.0:
                y_scrollbar.grid_remove()
            else:
                y_scrollbar.grid()
            y_scrollbar.set(first, last)

        content_canvas.configure(yscrollcommand=on_yscroll)

        def update_scroll_region(_event=None):
            bbox = content_canvas.bbox("all")
            if bbox:
                # Pin the top-left to (0, 0) so the content can never be scrolled above its
                # first line.
                content_canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3]))

        def update_content_width(event):
            content_canvas.itemconfigure(content_window, width=event.width)

        content_frame.bind("<Configure>", update_scroll_region)
        content_canvas.bind("<Configure>", update_content_width)
        content_canvas.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        y_scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))

        # Let the mouse wheel scroll from anywhere in the window, not just over the scrollbar.
        # The Toplevel is in every descendant's bindtags, so binding here catches wheel events
        # over any child widget. (macOS/Windows use <MouseWheel>; X11 uses Button-4/5.)
        def on_mousewheel(event):
            # Don't scroll (or "float" the content) when everything already fits the window.
            first, last = content_canvas.yview()
            if first <= 0.0 and last >= 1.0:
                return
            if event.num == 4:
                content_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                content_canvas.yview_scroll(1, "units")
            elif event.delta:
                step = -int(event.delta) if sys.platform == "darwin" else -int(event.delta / 120)
                content_canvas.yview_scroll(step or (-1 if event.delta > 0 else 1), "units")

        info_window.bind("<MouseWheel>", on_mousewheel)
        info_window.bind("<Button-4>", on_mousewheel)
        info_window.bind("<Button-5>", on_mousewheel)

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
            for index, action in enumerate(actions):
                # Actions are (label, command) or (label, command, style).
                label, command = action[0], action[1]
                button_style = action[2] if len(action) > 2 else "TButton"
                button = ttk.Button(action_frame, text=label, command=command, style=button_style)
                button.grid(row=0, column=index, padx=(0 if index == 0 else 6, 0))

    def _add_info_section(self, parent, title, row):
        title_label = ttk.Label(parent, text=title, font=("Helvetica", 12, "bold"))
        title_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(14, 6))
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.grid(row=row + 1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 6))
        return row + 2

    def _add_info_row(self, parent, row, label, value, action=None, label_image=None):
        if label_image is not None:
            # A small source logo stands in for the text label (used by "Merged from" rows).
            # The column is already sized by the text labels above, so anchor east to align it.
            label_widget = ttk.Label(parent, image=label_image, anchor=tk.E)
        else:
            label_widget = ttk.Label(parent, text=f"{label}:", width=18, anchor=tk.E)
        label_widget.grid(row=row, column=0, sticky=tk.NE, padx=(0, 14), pady=3)

        # Pin the value to the top of the row (tk.N) so it lines up with the label
        # instead of vertically centering and appearing a line below it.
        value_frame = ttk.Frame(parent)
        value_frame.grid(row=row, column=1, sticky=(tk.W, tk.E, tk.N), pady=3)
        value_frame.columnconfigure(0, weight=1)

        value_widget = ttk.Label(value_frame, text=str(value), wraplength=520, justify=tk.LEFT, anchor=tk.W)
        value_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N))

        if action:
            action_label, command = action
            button = ttk.Button(value_frame, text=action_label, command=command)
            # Pin the button to the top of the row (tk.NE) so it lines up with the label and
            # the first line of the value instead of centering when the value wraps.
            button.grid(row=0, column=1, sticky=tk.NE, padx=(10, 0))

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
        for index in range(12):
            self.display_frame.rowconfigure(index, weight=0)
            self.display_frame.columnconfigure(index, weight=0)

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
        self.app_settings.set(USE_DISPLAY_WINDOWS, bool(self.use_display_windows_var.get()))
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
        self._show_display(
            "Settings",
            lambda parent: settings_view.build(self, parent),
            geometry="800x660",
        )

    def show_temporary_playlists_display(self):
        self._show_display(
            "Temporary Playlists",
            self._build_temporary_playlists_display,
            geometry="820x520",
        )

    def _build_temporary_playlists_display(self, parent):
        temporary_playlists_view.build(self, parent)

    def show_temporary_playlist_details_window(self, record):
        temporary_playlists_view.show_details(self, record)

    def show_youtube_music_auth_display(self):
        self._show_display("Connect YouTube Music", self._build_youtube_music_auth_display, geometry="820x620")

    def show_youtube_music_browser_auth_display(self):
        self._show_display("Set YouTube Music Queue Headers", self._build_youtube_music_browser_auth_display, geometry="860x660")

    def _build_youtube_music_browser_auth_display(self, parent):
        youtube_music_auth_views.build_browser_auth(self, parent)

    def save_youtube_music_browser_headers(self, headers_text, status_var, test_button=None):
        headers_raw = headers_text.get("1.0", tk.END).strip()
        try:
            self.youtube_account.store_browser_auth_headers(headers_raw)
            self.youtube_queue_auth_error = None
            self.youtube_queue_headers_verified = False
            self.browser_authenticated_ytmusic = self._build_browser_authenticated_ytmusic()
            if self.browser_authenticated_ytmusic is None:
                raise RuntimeError("The saved headers could not initialize a YouTube Music session.")
        except Exception as e:
            self.youtube_queue_auth_error = str(e)
            status_var.set(f"Status: headers not saved - {e}")
            return

        if test_button:
            test_button.state(["!disabled"])
        status_var.set("Status: browser headers saved. Use Test Saved Headers to verify them.")

    def test_youtube_music_browser_headers(self, status_var, test_button=None):
        client = self._youtube_music_queue_client()
        if client is None:
            status_var.set("Status: no saved browser headers. Paste headers and save them first.")
            return

        if test_button:
            test_button.state(["disabled"])
        status_var.set("Status: testing saved browser headers...")

        def worker():
            try:
                client.get_library_playlists(limit=1)
            except Exception as e:
                self.root.after(0, lambda error=e: finish(False, error))
                return
            self.root.after(0, lambda: finish(True, None))

        def finish(success, error):
            if test_button:
                test_button.state(["!disabled"])
            if success:
                self.youtube_queue_auth_error = None
                self.youtube_queue_headers_verified = True
                status_var.set("Status: browser headers worked.")
            else:
                self.youtube_queue_headers_verified = False
                self.browser_authenticated_ytmusic = None
                self.youtube_queue_auth_error = self._format_browser_auth_test_error(error)
                status_var.set(f"Status: browser headers failed - {self.youtube_queue_auth_error}")

        threading.Thread(target=worker, daemon=True).start()

    def _format_browser_auth_test_error(self, error):
        error_text = str(error)
        if "Expecting value" in error_text:
            return (
                "YouTube Music did not return a usable API response. In Chrome, copy a logged-in "
                "POST /browse request from music.youtube.com using Copy as fetch (Node.js), then save again."
            )
        if "401" in error_text or "Unauthorized" in error_text:
            return "the saved browser session is not authorized. Sign in to music.youtube.com and copy fresh /browse headers."
        return error_text

    def _is_browser_auth_refresh_error(self, error):
        error_text = str(error)
        return (
            "Expecting value" in error_text
            or "401" in error_text
            or "Unauthorized" in error_text
            or "browser auth" in error_text
        )

    def _mark_youtube_queue_auth_failed(self, error):
        self.youtube_queue_headers_verified = False
        self.browser_authenticated_ytmusic = None
        self.youtube_queue_auth_error = self._format_browser_auth_test_error(error)

    def _prompt_browser_auth_refresh(self, error):
        """Flag the queue auth as failed and offer a one-click jump to re-paste headers.

        Used whenever a queue/delete request fails with an auth-like error — typically the
        saved session expired because Google rotated it (not because the user signed out).
        """
        self._mark_youtube_queue_auth_failed(error)
        detail = self.youtube_queue_auth_error or str(error)
        should_refresh = messagebox.askyesno(
            "YouTube Music Session Expired",
            (
                "Your saved YouTube Music queue headers were rejected. This usually means the "
                "session expired — Google rotates it periodically, so it happens even if you "
                "never signed out.\n\n"
                f"{detail}\n\n"
                "Re-paste fresh headers now?"
            ),
            parent=self.root,
        )
        if should_refresh:
            self.show_youtube_music_browser_auth_display()

    def _build_youtube_music_auth_display(self, parent):
        youtube_music_auth_views.build_oauth(self, parent)

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

    def disconnect_youtube_music_browser_auth(self):
        if not self.youtube_account.has_browser_auth():
            messagebox.showinfo("YouTube Music Queue", "No queue browser headers are saved.")
            return

        should_disconnect = messagebox.askyesno(
            "Clear Queue Headers",
            "Remove the saved YouTube Music browser request headers from this computer?"
        )
        if not should_disconnect:
            return

        self.youtube_account.disconnect_browser_auth()
        self.browser_authenticated_ytmusic = None
        self.youtube_queue_auth_error = None
        self.youtube_queue_headers_verified = False
        messagebox.showinfo("YouTube Music Queue", "YouTube Music queue headers have been cleared.")
        self.show_settings_display()

    def _find_matching_tracks(self, query):
        query_terms = [term for term in text_utils.normalize_search_text(query).split() if term]
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
                searchable_text = text_utils.normalize_search_text(f"{title} {artist}")

                if all(term in searchable_text for term in query_terms):
                    track_key = playlist_store.normalize_song_key(title, artist)
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

    def _show_youtube_queue_actions(self):
        value = os.environ.get(self.YOUTUBE_QUEUE_ACTIONS_ENV_VAR, "")
        return value.lower() in {"1", "true", "yes", "on"}

    def play_selection_in_youtube_music(self):
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first.")
            return

        selected_playlist_keys = self._selected_sidebar_playlist_keys()
        if not selected_playlist_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist.")
            return

        youtube_playlists, skipped_playlists = playlist_store.select_youtube_playlist_sources(
            self.saved_playlists, selected_playlist_keys
        )
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

        if not self._is_youtube_music_queue_connected():
            should_connect = messagebox.askyesno(
                "Set Queue Headers",
                (
                    "Creating a temporary YouTube Music playlist currently requires copied "
                    "YouTube Music browser request headers. Set queue headers now?"
                )
            )
            if should_connect:
                self.show_youtube_music_browser_auth_display()
            return

        self._create_temporary_youtube_music_playlist(youtube_playlists)

    def _create_temporary_youtube_music_playlist(self, youtube_playlists):
        client = self._youtube_music_queue_client()
        if client is None:
            messagebox.showerror(
                "YouTube Music",
                "The saved YouTube Music queue headers could not be loaded. Refresh them in Settings."
            )
            self.show_youtube_music_browser_auth_display()
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
        video_ids = self._temporary_youtube_playlist_video_ids(youtube_playlists)
        return self.queue_service.create_temp_playlist(client, video_ids, youtube_playlists, set_status)

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

        # De-duplicate while preserving first-seen order. A song that appears in
        # several selected playlists must only be sent once; YouTube Music rejects
        # re-adds of a video already in the playlist, which would otherwise show up
        # as "skipped" songs. A video is treated as a preferred seed if any of its
        # occurrences is preferred.
        video_ids = []
        preferred_by_id = {}
        for video_id, preferred in video_entries:
            if video_id in preferred_by_id:
                if preferred:
                    preferred_by_id[video_id] = True
                continue
            preferred_by_id[video_id] = preferred
            video_ids.append(video_id)

        for index, video_id in enumerate(video_ids):
            if preferred_by_id.get(video_id):
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

    def _finish_temporary_playlist_creation(self, progress_window, title, temp_playlist_id, error, skipped_video_ids=None):
        if progress_window.winfo_exists():
            progress_window.destroy()

        if error:
            if self._is_browser_auth_refresh_error(error):
                self._prompt_browser_auth_refresh(error)
                return

            messagebox.showerror("YouTube Music", f"Failed to create the temporary playlist: {error}")
            return

        self.youtube_account.open_playlist(temp_playlist_id)
        skipped_video_ids = skipped_video_ids or []
        skipped_message = ""
        if skipped_video_ids:
            examples = ", ".join(item["video_id"] for item in skipped_video_ids[:5])
            more = "..." if len(skipped_video_ids) > 5 else ""
            reasons = self._summarize_skip_reasons(skipped_video_ids)
            reason_message = f"\nMost common reason(s): {reasons}." if reasons else ""
            skipped_message = (
                f"\n\nSkipped {len(skipped_video_ids)} song"
                f"{'' if len(skipped_video_ids) == 1 else 's'} that YouTube Music rejected"
                f" ({examples}{more})."
                "\nThis usually means the track is unavailable, private, or region-locked."
                f"{reason_message}"
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

    def _summarize_skip_reasons(self, skipped_video_ids, limit=3):
        distinct = []
        for item in skipped_video_ids or []:
            reason = str((item or {}).get("error") or "").strip()
            if reason and reason not in distinct:
                distinct.append(reason)
            if len(distinct) >= limit:
                break
        return " | ".join(distinct)

    def delete_temporary_youtube_playlists(self, prompt=True, records=None):
        if records is None:
            records = self.youtube_account.load_temporary_playlists()
        if not records:
            messagebox.showinfo("Temporary Playlists", "There are no temporary YouTube Music playlists to delete.")
            return

        client = self._youtube_music_queue_client()
        if client is None:
            messagebox.showerror(
                "YouTube Music",
                "Refresh YouTube Music queue headers before deleting temporary playlists."
            )
            self.show_youtube_music_browser_auth_display()
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
            deleted_ids, failed = self.queue_service.delete_temp_playlists(
                client,
                records,
                lambda text: self.root.after(0, lambda: status_var.set(text)),
            )
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
            for record, error in failed:
                print(f"Failed to delete temporary playlist {record.playlist_id!r} "
                      f"({record.title!r}): {error!r}")

            auth_error = next(
                (error for _record, error in failed if self._is_browser_auth_refresh_error(error)),
                None,
            )
            if auth_error is not None:
                # Expired session: refreshing the display first, then offer one-click recovery.
                self._refresh_temporary_playlist_views()
                self._prompt_browser_auth_refresh(auth_error)
                return

            detail_lines = [
                f"• {record.title}: {self._format_browser_auth_test_error(error)}"
                for record, error in failed[:5]
            ]
            if len(failed) > 5:
                detail_lines.append(f"• …and {len(failed) - 5} more")
            detail = "\n".join(detail_lines)

            messagebox.showwarning(
                "Temporary Playlist Cleanup",
                (
                    f"Deleted {len(deleted_ids)} playlist"
                    f"{'' if len(deleted_ids) == 1 else 's'}, but {len(failed)} could not be "
                    f"deleted:\n\n{detail}\n\nIf a playlist was already removed on "
                    "music.youtube.com it can't be deleted again — you can clear it from this "
                    "list with no further effect."
                )
            )
        else:
            messagebox.showinfo(
                "Temporary Playlist Cleanup",
                f"Deleted {len(deleted_ids)} temporary playlist{'' if len(deleted_ids) == 1 else 's'}."
            )

        self._refresh_temporary_playlist_views()

    def _refresh_temporary_playlist_views(self):
        if self.current_display_view == 'settings':
            self.show_settings_display()
        elif self.current_display_view == 'temporary_playlists':
            self.show_temporary_playlists_display()

    def _open_playlist_url(self, playlist_key):
        pl_data = self.saved_playlists.get(playlist_key)
        if not pl_data:
            messagebox.showinfo("No Selection", "Select a saved playlist first.")
            return

        source, playlist_id = playlist_store.normalize_playlist_identity(playlist_key, pl_data)
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

    def show_playlist_details_window(self, playlist_key, on_change=None):
        saved_playlists_view.show_details(self, playlist_key, on_change=on_change)

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
                entry_key = playlist_store.combined_track_key(track)
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
            return text_utils.normalize_search_text(value)

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
        self._show_display(
            "Search Results",
            lambda parent: search_results_view.build(self, parent, query, sorted_results),
        )
    
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
        saved_playlists_view.build(self, parent)

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
        playlist_selection_view.build(self, selected_keys)

    def show_combined_songs_display(self, playlist_keys, live=False):
        self._show_display(
            "Combined Songs",
            lambda parent: combined_songs_view.build(self, parent, playlist_keys, live),
            geometry="1080x620",
        )

    def _set_playlist_selection(self, playlist_vars, selected):
        for _, selected_var in playlist_vars:
            selected_var.set(selected)
        self._refresh_live_combined_if_active()

    def _selected_playlist_keys(self, playlist_vars):
        return [playlist_key for playlist_key, selected_var in playlist_vars if selected_var.get()]

    def _build_playlist_checkbox_selector(self, parent, on_change=None, selected_keys=None, highlight_selected=False):
        return playlist_checkbox_selector.build(
            self, parent, on_change=on_change, selected_keys=selected_keys,
            highlight_selected=highlight_selected,
        )

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
        self._show_display(
            "Selected Playlist Duplicates",
            lambda parent: duplicates_view.build(self, parent, duplicate_entries, selected_count),
            geometry="1080x620",
        )
    
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

                    source, playlist_id = playlist_store.normalize_playlist_identity(playlist_key, pl_data)
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
