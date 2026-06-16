"""Combined Songs view: the default landing screen that merges the selected
playlists' tracks into one sortable, filterable list (with live refresh when
driven by the sidebar selection).

Tk view builder extracted from the UI controller (step 2 of decomposing ui.py).
Takes the controller as an explicit dependency for track collection/sorting,
source logos, find controls, and the shared song detail/play actions.
"""
import tkinter as tk
from tkinter import ttk

from app.services import text_utils


def build(controller, parent, playlist_keys, live=False):
    playlist_count = len(playlist_keys)
    controller.current_display_view = "combined"
    controller._active_combined_refresh = None
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

    results_playlist_keys = controller._selected_sidebar_playlist_keys if live else playlist_keys
    build_results(controller, results_frame, results_playlist_keys, live=live)


def build_results(controller, parent, playlist_keys, live=False):
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)

    toolbar_frame = ttk.Frame(parent)
    toolbar_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    toolbar_frame.columnconfigure(5, weight=1)

    sort_label = ttk.Label(toolbar_frame, text="Sort by:")
    sort_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=(0, 6))

    sort_var = tk.StringVar(value="Title (A-Z)")
    sort_combo = ttk.Combobox(
        toolbar_frame,
        textvariable=sort_var,
        values=list(controller.COMBINED_SORT_OPTIONS.keys()),
        state="readonly",
        width=24,
    )
    sort_combo.grid(row=0, column=1, sticky=tk.W, pady=(0, 6))

    display_find_var = tk.StringVar()
    find_label, find_entry = controller._create_display_find_controls(toolbar_frame, display_find_var)
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

    song_columns = ("title", "artist", "playlists")

    songs_tree = ttk.Treeview(
        table_frame,
        columns=song_columns,
        show="tree headings",
        style="SourceLogo.Treeview",
        yscrollcommand=y_scrollbar.set,
        xscrollcommand=x_scrollbar.set,
    )
    songs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    y_scrollbar.config(command=songs_tree.yview)
    x_scrollbar.config(command=songs_tree.xview)

    songs_tree.heading("#0", text="")
    songs_tree.heading("title", text="Title")
    songs_tree.heading("artist", text="Artist")
    songs_tree.heading("playlists", text="Playlists")

    songs_tree.column("#0", width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
    songs_tree.column("title", width=260, minwidth=160, stretch=False)
    songs_tree.column("artist", width=190, minwidth=120, stretch=False)
    # Smaller by default but stretches with the window and is resizable; the full
    # playlist list (untruncated) is available in the song's Details window.
    songs_tree.column("playlists", width=320, minwidth=140, stretch=True)

    entry_by_item = {}
    visible_entries = []

    # Button commands read this list so queued playback follows the current sort/find view.
    details_button = ttk.Button(
        toolbar_frame,
        text="Details",
        command=lambda: controller._show_selected_entry_details(songs_tree, entry_by_item),
    )
    details_button.grid(row=1, column=2, sticky=tk.W, padx=(10, 4))

    play_button = ttk.Button(
        toolbar_frame,
        text="Play",
        command=lambda: controller._play_selected_tree_entry(songs_tree, entry_by_item),
    )
    play_button.grid(row=1, column=3, sticky=tk.W, padx=4)

    def refresh_results(*_):
        nonlocal visible_entries
        selected_playlist_keys = playlist_keys() if callable(playlist_keys) else playlist_keys
        entries = controller._collect_combined_tracks(selected_playlist_keys, merge_duplicates=True)
        entries = controller._sort_combined_tracks(entries, sort_var.get())
        filtered_entries = [
            entry
            for entry in entries
            if text_utils.matches_find_query(
                [
                    entry["title"],
                    entry["artist"],
                    controller._format_playlist_occurrences(entry, limit=None),
                    ", ".join(sorted(controller._source_name(source) for source in entry["sources"])),
                ],
                display_find_var.get(),
            )
        ]
        visible_entries = filtered_entries

        entry_by_item.clear()
        for item_id in songs_tree.get_children():
            songs_tree.delete(item_id)

        if not filtered_entries:
            message = "No songs found for the selected playlists."
            if entries:
                message = "No songs match the current find text."
            songs_tree.insert("", tk.END, values=(message, "", ""))
        else:
            for entry in filtered_entries:
                playlist_text = controller._format_playlist_occurrences(entry, controller.PLAYLIST_DISPLAY_LIMIT)
                row_values = (entry["title"], entry["artist"], playlist_text)
                item_id = songs_tree.insert(
                    "",
                    tk.END,
                    image=controller._source_logo_for_sources(entry["sources"]),
                    values=row_values,
                )
                entry_by_item[item_id] = entry

        if display_find_var.get().strip() and len(filtered_entries) != len(entries):
            count_var.set(f"{len(filtered_entries)} of {len(entries)} songs")
        else:
            count_var.set(f"{len(entries)} songs")

    sort_combo.bind("<<ComboboxSelected>>", refresh_results)
    songs_tree.bind("<Double-1>", lambda _event: controller._show_selected_entry_details(songs_tree, entry_by_item))
    # Right-click menu to add/remove the song on the user's YouTube playlists.
    # Bind every right-click variant (platforms differ: Button-3, macOS Button-2 / Ctrl-click).
    for sequence in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
        songs_tree.bind(
            sequence,
            lambda event: controller._show_song_context_menu(event, songs_tree, entry_by_item),
        )
    display_find_var.trace_add("write", refresh_results)
    if live:
        controller._active_combined_refresh = refresh_results

    refresh_results()
