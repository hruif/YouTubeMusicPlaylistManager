"""Duplicates view: the "Selected Playlist Duplicates" screen — a filterable song
tree of tracks that appear more than once across the selected playlists.

Tk view builder extracted from the UI controller (step 2 of decomposing ui.py).
"""
import tkinter as tk
from tkinter import ttk

from app.services import text_utils


def build(controller, parent, duplicate_entries, selected_count):
    controller.current_display_view = "duplicates"
    controller._active_combined_refresh = None
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
    find_label, find_entry = controller._create_display_find_controls(find_frame, display_find_var)
    find_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
    find_entry.grid(row=0, column=1, sticky=tk.W)

    table_frame = ttk.Frame(parent)
    table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
    y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
    x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    duplicate_columns = ("title", "artist", "custom_name", "playlists")

    duplicates_tree = ttk.Treeview(
        table_frame,
        columns=duplicate_columns,
        show="tree headings",
        style="SourceLogo.Treeview",
        yscrollcommand=y_scrollbar.set,
        xscrollcommand=x_scrollbar.set,
    )
    duplicates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    y_scrollbar.config(command=duplicates_tree.yview)
    x_scrollbar.config(command=duplicates_tree.xview)

    duplicates_tree.heading("#0", text="")
    duplicates_tree.heading("title", text="Title")
    duplicates_tree.heading("artist", text="Artist")
    duplicates_tree.heading("custom_name", text="Custom Name")
    duplicates_tree.heading("playlists", text="Playlists")

    duplicates_tree.column("#0", width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
    duplicates_tree.column("title", width=260, minwidth=160, stretch=False)
    duplicates_tree.column("artist", width=190, minwidth=120, stretch=False)
    duplicates_tree.column("custom_name", width=180, minwidth=120, stretch=False)
    # Smaller by default but stretches with the window and is resizable; the full
    # playlist list (untruncated) is available in the song's Details window.
    duplicates_tree.column("playlists", width=320, minwidth=140, stretch=True)
    duplicates_tree.configure(displaycolumns=controller.song_tree_display_columns())

    entry_by_item = {}
    visible_entries = []

    # Queue playback intentionally uses the filtered duplicate rows currently on screen.
    details_button = ttk.Button(
        header_frame,
        text="Details",
        command=lambda: controller._show_selected_entry_details(duplicates_tree, entry_by_item),
    )
    details_button.grid(row=1, column=1, sticky=tk.W, padx=(10, 4), pady=(8, 0))

    play_button = ttk.Button(
        header_frame,
        text="Play",
        command=lambda: controller._play_selected_tree_entry(duplicates_tree, entry_by_item),
    )
    play_button.grid(row=1, column=2, sticky=tk.W, padx=4, pady=(8, 0))

    def refresh_duplicate_rows(*_):
        nonlocal visible_entries
        duplicates_tree.configure(displaycolumns=controller.song_tree_display_columns())
        entry_by_item.clear()
        for item_id in duplicates_tree.get_children():
            duplicates_tree.delete(item_id)

        visible_entries = [
            entry
            for entry in duplicate_entries
            if text_utils.matches_find_query(
                [
                    entry["title"],
                    entry["artist"],
                    controller._entry_custom_name(entry),
                    controller._format_playlist_occurrences(entry, limit=None),
                    ", ".join(sorted(controller._source_name(source) for source in entry["sources"])),
                ],
                display_find_var.get(),
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
            duplicates_tree.insert("", tk.END, values=(message, "", "", ""))
            return

        for entry in visible_entries:
            playlist_text = controller._format_playlist_occurrences(entry, controller.PLAYLIST_DISPLAY_LIMIT)
            row_values = (
                controller._entry_display_title(entry),
                entry["artist"],
                controller._entry_custom_name(entry),
                playlist_text,
            )
            item_id = duplicates_tree.insert(
                "",
                tk.END,
                image=controller._source_logo_for_sources(entry["sources"]),
                values=row_values,
            )
            entry_by_item[item_id] = entry

    duplicates_tree.bind("<Double-1>", lambda _event: controller._show_selected_entry_details(duplicates_tree, entry_by_item))
    # Right-click menu to add/remove the song on the user's YouTube playlists (same as View Songs).
    for sequence in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
        duplicates_tree.bind(
            sequence,
            lambda event: controller._show_song_context_menu(event, duplicates_tree, entry_by_item),
        )
    display_find_var.trace_add("write", refresh_duplicate_rows)
    refresh_duplicate_rows()
