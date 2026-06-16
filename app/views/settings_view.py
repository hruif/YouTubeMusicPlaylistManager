"""Settings view: the Settings screen (display options, YouTube Music account,
temporary playlists, experimental queue headers, updates).

Tk view builder extracted from the UI controller (step 2 of decomposing ui.py).
Takes the controller as an explicit dependency and calls back into it for state
variables, status strings, and navigation.
"""
import tkinter as tk
from tkinter import ttk

from app.app_info import APP_VERSION


def build(controller, parent):
    controller.current_display_view = "settings"
    parent.columnconfigure(0, weight=1)

    title = ttk.Label(parent, text="Settings", font=("Helvetica", 15, "bold"))
    title.grid(row=0, column=0, sticky=tk.W, pady=(0, 14))

    display_frame = ttk.LabelFrame(parent, text="Display", padding="12")
    display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
    display_frame.columnconfigure(0, weight=1)

    display_window_setting = ttk.Checkbutton(
        display_frame,
        text="Open display output in separate windows",
        variable=controller.use_display_windows_var,
        command=controller._on_display_mode_changed,
    )
    display_window_setting.grid(row=0, column=0, sticky=tk.W)

    description = ttk.Label(
        display_frame,
        text=(
            "When enabled, saved playlists, combined songs, "
            "duplicate results, and settings open in windows. The main display "
            "is used for playlist selection."
        ),
        wraplength=520,
    )
    description.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))

    account_frame = ttk.LabelFrame(parent, text="YouTube Music Account", padding="12")
    account_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(12, 0))
    account_frame.columnconfigure(0, weight=1)

    status_label = ttk.Label(account_frame, text=f"Status: {controller._youtube_music_auth_status()}")
    status_label.grid(row=0, column=0, sticky=tk.W)

    account_actions = ttk.Frame(account_frame)
    account_actions.grid(row=0, column=1, sticky=tk.E, padx=(12, 0))

    connect_button = ttk.Button(
        account_actions,
        text="Reconnect" if controller._is_youtube_music_connected() else "Connect",
        command=controller.show_youtube_music_auth_display,
    )
    connect_button.grid(row=0, column=0, sticky=tk.E, padx=(0, 6))

    disconnect_button = ttk.Button(
        account_actions,
        text="Disconnect",
        command=controller.disconnect_youtube_music,
    )
    disconnect_button.grid(row=0, column=1, sticky=tk.E)
    if not controller._is_youtube_music_connected():
        disconnect_button.state(["disabled"])

    temp_frame = ttk.LabelFrame(parent, text="Temporary Playlists", padding="12")
    temp_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(12, 0))
    temp_frame.columnconfigure(0, weight=1)

    temp_records = controller.youtube_account.load_temporary_playlists()
    temp_label = ttk.Label(
        temp_frame,
        text=f"Temporary playlists on your account: {len(temp_records)}",
    )
    temp_label.grid(row=0, column=0, sticky=tk.W)

    auto_delete_check = ttk.Checkbutton(
        temp_frame,
        text="Delete temporary playlists automatically when I close the app",
        variable=controller.auto_delete_temp_on_exit_var,
        command=controller._on_auto_delete_temp_changed,
    )
    auto_delete_check.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))

    temp_actions = ttk.Frame(temp_frame)
    temp_actions.grid(row=0, column=1, rowspan=2, sticky=tk.E, padx=(12, 0))

    view_temp_button = ttk.Button(
        temp_actions,
        text="View Temporary Playlists",
        command=controller.show_temporary_playlists_display,
    )
    view_temp_button.grid(row=0, column=0, sticky=tk.E, padx=(0, 6))
    if not temp_records:
        view_temp_button.state(["disabled"])

    cleanup_button = ttk.Button(
        temp_actions,
        text="Delete All",
        command=controller.delete_temporary_youtube_playlists,
    )
    cleanup_button.grid(row=0, column=1, sticky=tk.E)
    if not temp_records:
        cleanup_button.state(["disabled"])

    queue_frame = ttk.LabelFrame(parent, text="Experimental YouTube Music Queue", padding="12")
    queue_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(12, 0))
    queue_frame.columnconfigure(0, weight=1)

    queue_status_label = ttk.Label(
        queue_frame,
        text=f"Status: {controller._youtube_music_queue_auth_status()}",
    )
    queue_status_label.grid(row=0, column=0, sticky=tk.W)

    queue_description = ttk.Label(
        queue_frame,
        text=(
            "\"Play in YouTube Music\" creates a private temporary playlist using copied YouTube "
            "Music browser request headers (not the YouTube Data API, so there is no quota). "
            "Set them up here once, and refresh them if playlist creation starts failing."
        ),
        wraplength=520,
    )
    queue_description.grid(row=1, column=0, sticky=tk.W, pady=(6, 0))

    queue_actions = ttk.Frame(queue_frame)
    queue_actions.grid(row=0, column=1, rowspan=2, sticky=tk.E, padx=(12, 0))

    queue_headers_button = ttk.Button(
        queue_actions,
        text="Set Queue Headers",
        command=controller.show_youtube_music_browser_auth_display,
    )
    queue_headers_button.grid(row=0, column=0, sticky=tk.E, padx=(0, 6))

    clear_queue_headers_button = ttk.Button(
        queue_actions,
        text="Clear Headers",
        command=controller.disconnect_youtube_music_browser_auth,
    )
    clear_queue_headers_button.grid(row=0, column=1, sticky=tk.E)
    if not controller.youtube_account.has_browser_auth():
        clear_queue_headers_button.state(["disabled"])

    updates_frame = ttk.LabelFrame(parent, text="Updates", padding="12")
    updates_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=(12, 0))
    updates_frame.columnconfigure(0, weight=1)

    version_label = ttk.Label(updates_frame, text=f"Current version: {APP_VERSION}")
    version_label.grid(row=0, column=0, sticky=tk.W)

    check_button = ttk.Button(
        updates_frame,
        text="Check for Updates",
        command=lambda: controller.check_for_updates(silent=False),
    )
    check_button.grid(row=0, column=1, sticky=tk.E, padx=(12, 0))
