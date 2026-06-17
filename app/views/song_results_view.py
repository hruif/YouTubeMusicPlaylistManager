"""Song results view: a filterable song table (title / artist / custom name / playlists)
shared by the "Find Duplicates in Selection" and "Find Unavailable in Selection" finders.

Generalized from the original duplicates view. The right-click menu edits (add/remove) the
listed songs on your YouTube playlists, so a results screen doubles as a cleanup tool.
Callers pass `view_id` (for current_display_view), a `title` noun, and the `empty_message`
shown when there are no results.
"""
import tkinter as tk
from tkinter import ttk

from app.services import text_utils


def build(controller, parent, entries, *, view_id, title, empty_message):
    controller.current_display_view = view_id
    controller._active_combined_refresh = None
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)

    header_frame = ttk.Frame(parent)
    header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    header_frame.columnconfigure(0, weight=1)

    title_var = tk.StringVar()
    title_label = ttk.Label(header_frame, textvariable=title_var, font=("Helvetica", 15, "bold"))
    title_label.grid(row=0, column=0, sticky=tk.W)

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

    columns = ("title", "artist", "custom_name", "playlists")
    tree = ttk.Treeview(
        table_frame, columns=columns, show="tree headings", style="SourceLogo.Treeview",
        yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set,
    )
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    y_scrollbar.config(command=tree.yview)
    x_scrollbar.config(command=tree.xview)

    tree.heading("#0", text="")
    tree.heading("title", text="Title")
    tree.heading("artist", text="Artist")
    tree.heading("custom_name", text="Custom Name")
    tree.heading("playlists", text="Playlists")
    tree.column("#0", width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
    tree.column("title", width=260, minwidth=160, stretch=False)
    tree.column("artist", width=190, minwidth=120, stretch=False)
    tree.column("custom_name", width=180, minwidth=120, stretch=False)
    # Smaller by default but stretches with the window; the full list is in a song's Details.
    tree.column("playlists", width=320, minwidth=140, stretch=True)
    tree.configure(displaycolumns=controller.song_tree_display_columns())

    entry_by_item = {}

    details_button = ttk.Button(
        header_frame, text="Details",
        command=lambda: controller._show_selected_entry_details(tree, entry_by_item),
    )
    details_button.grid(row=1, column=1, sticky=tk.W, padx=(10, 4), pady=(8, 0))
    play_button = ttk.Button(
        header_frame, text="Play",
        command=lambda: controller._play_selected_tree_entry(tree, entry_by_item),
    )
    play_button.grid(row=1, column=2, sticky=tk.W, padx=4, pady=(8, 0))

    def refresh_rows(*_):
        tree.configure(displaycolumns=controller.song_tree_display_columns())
        entry_by_item.clear()
        for item_id in tree.get_children():
            tree.delete(item_id)

        visible = [
            entry for entry in entries
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

        if display_find_var.get().strip() and len(visible) != len(entries):
            title_var.set(f"{title} ({len(visible)} of {len(entries)} shown)")
        else:
            title_var.set(f"{title} ({len(entries)} found)")

        if not visible:
            message = "No songs match the current find text." if entries else empty_message
            tree.insert("", tk.END, values=(message, "", "", ""))
            return

        for entry in visible:
            playlist_text = controller._format_playlist_occurrences(entry, controller.PLAYLIST_DISPLAY_LIMIT)
            row_values = (
                controller._entry_display_title(entry),
                entry["artist"],
                controller._entry_custom_name(entry),
                playlist_text,
            )
            item_id = tree.insert(
                "", tk.END,
                image=controller._source_logo_for_sources(entry["sources"]),
                values=row_values,
            )
            entry_by_item[item_id] = entry

    tree.bind("<Double-1>", lambda _event: controller._show_selected_entry_details(tree, entry_by_item))
    # Right-click to add/remove the listed songs on your YouTube playlists (same as View Songs).
    for sequence in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
        tree.bind(sequence, lambda event: controller._show_song_context_menu(event, tree, entry_by_item))
    display_find_var.trace_add("write", refresh_rows)
    refresh_rows()
