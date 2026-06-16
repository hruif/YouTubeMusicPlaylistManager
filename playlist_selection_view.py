"""Playlist Selection view: the playlist-picker shown in the main display area when
"separate windows" mode is on (so the main area still drives the live selection).

Tk view builder extracted from the UI controller (step 2 of decomposing ui.py).
It renders directly into controller.display_frame.
"""
import tkinter as tk
from tkinter import ttk


def build(controller, selected_keys=None):
    controller.current_display_view = "playlist_selection"
    controller._active_combined_refresh = None
    if selected_keys is None:
        selected_keys = set(controller._selected_playlist_keys_from_active_display())

    controller._clear_display_frame()

    header_frame = ttk.Frame(controller.display_frame)
    header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    header_frame.columnconfigure(0, weight=1)

    title = ttk.Label(header_frame, text="Selected Playlists", font=("Helvetica", 15, "bold"))
    title.grid(row=0, column=0, sticky=tk.W)

    settings_button = ttk.Button(header_frame, text="Settings", command=controller.show_settings_display)
    settings_button.grid(row=0, column=1, sticky=tk.E)

    selector_frame = ttk.LabelFrame(controller.display_frame, text="Playlists", padding=(8, 6))
    selector_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    controller.display_playlist_vars = controller._build_playlist_checkbox_selector(
        selector_frame,
        selected_keys=selected_keys,
        highlight_selected=True,
    )

    action_frame = ttk.Frame(controller.display_frame)
    action_frame.grid(row=2, column=0, sticky=tk.E, pady=(8, 0))

    select_all_button = ttk.Button(
        action_frame,
        text="Select All",
        command=lambda: controller._set_playlist_selection(controller.display_playlist_vars, True),
    )
    select_all_button.grid(row=0, column=0, padx=5)

    clear_button = ttk.Button(
        action_frame,
        text="Clear",
        command=lambda: controller._set_playlist_selection(controller.display_playlist_vars, False),
    )
    clear_button.grid(row=0, column=1, padx=5)

    controller.display_frame.columnconfigure(0, weight=1)
    controller.display_frame.rowconfigure(1, weight=1)
