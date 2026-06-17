"""Saved Playlists view: the "View Saved Playlists" list and the per-playlist
details window.

Tk view builders extracted from the UI controller (step 2 of decomposing ui.py).
They take the controller as an explicit dependency and call back into it for the
info-window toolkit, playlist data/persistence, source logos, and find controls.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from app.services import playlist_store
from app.services import text_utils


def build(controller, parent):
    controller.current_display_view = "playlists"
    controller._active_combined_refresh = None

    header_frame = ttk.Frame(parent)
    header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
    header_frame.columnconfigure(0, weight=1)

    title = ttk.Label(
        header_frame,
        text=f"Saved Playlists ({len(controller.saved_playlists)})",
        font=("Helvetica", 15, "bold"),
    )
    title.grid(row=0, column=0, sticky=tk.W)

    display_find_var = tk.StringVar()
    find_frame = ttk.Frame(header_frame)
    find_frame.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
    find_label, find_entry = controller._create_display_find_controls(find_frame, display_find_var)
    find_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
    find_entry.grid(row=0, column=1, sticky=tk.W)

    playlist_by_item = {}

    def selected_playlist_keys():
        return [
            playlist_by_item[item]
            for item in playlists_tree.selection()
            if item in playlist_by_item
        ]

    def selected_playlist_key():
        keys = selected_playlist_keys()
        if not keys:
            messagebox.showinfo("No Selection", "Select a saved playlist first.")
            return None
        return keys[0]

    def show_selected_playlist_details():
        playlist_key = selected_playlist_key()
        if playlist_key:
            show_details(controller, playlist_key, on_change=reload_playlist_rows)

    def delete_selected_playlists():
        keys = selected_playlist_keys()
        if not keys:
            messagebox.showinfo("No Selection", "Select a saved playlist to delete first.")
            return
        if len(keys) == 1:
            name = controller.saved_playlists.get(keys[0], {}).get("name", "this playlist")
            prompt = f"Remove “{name}” from your saved playlists?"
        else:
            prompt = f"Remove {len(keys)} saved playlists?"
        prompt += (
            "\n\nThis only removes the local copy in this app; it does not change the "
            "playlist on YouTube or Spotify."
        )
        if not messagebox.askyesno("Remove Saved Playlist", prompt):
            return
        controller._delete_saved_playlists(keys)
        reload_playlist_rows()

    details_button = ttk.Button(header_frame, text="Details", command=show_selected_playlist_details)
    details_button.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(8, 0))

    delete_button = ttk.Button(
        header_frame,
        text="Delete Selected",
        style="Danger.TButton",
        command=delete_selected_playlists,
    )
    delete_button.grid(row=1, column=2, sticky=tk.W, padx=(6, 0), pady=(8, 0))

    table_frame = ttk.Frame(parent)
    table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
    y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
    x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    playlists_tree = ttk.Treeview(
        table_frame,
        columns=("name", "source", "songs", "tracks", "id"),
        show="tree headings",
        style="SourceLogo.Treeview",
        yscrollcommand=y_scrollbar.set,
        xscrollcommand=x_scrollbar.set,
    )
    playlists_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    y_scrollbar.config(command=playlists_tree.yview)
    x_scrollbar.config(command=playlists_tree.xview)

    playlists_tree.heading("#0", text="")
    playlists_tree.heading("name", text="Playlist")
    playlists_tree.heading("source", text="Source")
    playlists_tree.heading("songs", text="Songs")
    playlists_tree.heading("tracks", text="Cached Tracks")
    playlists_tree.heading("id", text="ID")

    playlists_tree.column("#0", width=38, minwidth=38, stretch=False, anchor=tk.CENTER)
    playlists_tree.column("name", width=260, minwidth=160, stretch=False)
    playlists_tree.column("source", width=120, minwidth=90, stretch=False)
    playlists_tree.column("songs", width=80, minwidth=70, stretch=False, anchor=tk.CENTER)
    playlists_tree.column("tracks", width=110, minwidth=90, stretch=False, anchor=tk.CENTER)
    playlists_tree.column("id", width=260, minwidth=160, stretch=False)

    playlist_rows = []

    def load_playlist_rows():
        playlist_rows.clear()
        for playlist_key, pl_data in controller._sorted_playlist_items():
            source = pl_data.get("source", "youtube")
            videos = pl_data.get("videos", set())
            tracks = pl_data.get("tracks", [])
            row_values = (
                pl_data.get("name", "Unnamed"),
                controller._source_name(source),
                len(videos),
                len(tracks),
                pl_data.get("id", playlist_key),
            )
            playlist_rows.append((playlist_key, source, row_values))

    load_playlist_rows()

    def refresh_playlist_rows(*_):
        playlist_by_item.clear()
        for item_id in playlists_tree.get_children():
            playlists_tree.delete(item_id)

        visible_rows = [
            row
            for row in playlist_rows
            if text_utils.matches_find_query(row[2], display_find_var.get())
        ]

        if not visible_rows:
            playlists_tree.insert(
                "",
                tk.END,
                values=("No saved playlists match the current find text.", "", "", "", ""),
            )
            return

        for playlist_key, source, row_values in visible_rows:
            item_id = playlists_tree.insert(
                "",
                tk.END,
                image=controller._source_logo_image(source),
                values=row_values,
            )
            playlist_by_item[item_id] = playlist_key

    def reload_playlist_rows():
        load_playlist_rows()
        title.configure(text=f"Saved Playlists ({len(controller.saved_playlists)})")
        refresh_playlist_rows()

    def show_playlist_context_menu(event):
        row_id = playlists_tree.identify_row(event.y)
        if not row_id or row_id not in playlist_by_item:
            return
        playlists_tree.selection_set(row_id)
        playlist_key = playlist_by_item[row_id]
        pl_data = controller.saved_playlists.get(playlist_key, {})
        source, playlist_id = playlist_store.normalize_playlist_identity(playlist_key, pl_data)
        playlist_url = controller._playlist_url(source, playlist_id)

        menu = tk.Menu(playlists_tree, tearoff=0)
        menu.add_command(label="Playlist details", command=show_selected_playlist_details)
        if playlist_url:
            menu.add_command(
                label="Open in browser",
                command=lambda url=playlist_url: controller._open_external_url(url),
            )
        menu.add_command(label="Export…", command=lambda key=playlist_key: controller.export_playlist(key))
        menu.add_separator()
        menu.add_command(label="Delete", command=delete_selected_playlists)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    playlists_tree.bind("<Double-1>", lambda _event: show_selected_playlist_details())
    # Right-click a row for details / open in browser / delete (delete keeps its confirmation).
    for sequence in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
        playlists_tree.bind(sequence, show_playlist_context_menu)
    display_find_var.trace_add("write", refresh_playlist_rows)
    refresh_playlist_rows()

    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(1, weight=1)


def show_details(controller, playlist_key, on_change=None):
    pl_data = controller.saved_playlists.get(playlist_key)
    if not pl_data:
        messagebox.showinfo("No Selection", "Select a saved playlist first.")
        return

    source, playlist_id = playlist_store.normalize_playlist_identity(playlist_key, pl_data)
    source_name = controller._source_name(source)
    playlist_name = pl_data.get("name", "Unnamed Playlist")
    videos = pl_data.get("videos", set())
    tracks = pl_data.get("tracks", [])
    playlist_url = controller._playlist_url(source, playlist_id)

    details_window, outer_frame, content_frame = controller._create_info_window("Playlist Info", geometry="720x500")
    content_frame.columnconfigure(1, weight=1)

    def delete_this_playlist():
        if not messagebox.askyesno(
            "Remove Saved Playlist",
            f"Remove “{playlist_name}” from your saved playlists?\n\nThis only removes the "
            "local copy in this app; it does not change the playlist on YouTube or Spotify.",
            parent=details_window,
        ):
            return
        controller._delete_saved_playlists([playlist_key])
        if on_change:
            on_change()
        details_window.destroy()

    actions = []
    if playlist_url:
        actions.append(("Open", lambda: controller._open_external_url(playlist_url)))
    actions.append(("Export…", lambda: controller.export_playlist(playlist_key)))
    actions.append(("Delete", delete_this_playlist, "Danger.TButton"))
    actions.append(("Close", details_window.destroy))
    controller._add_info_header(outer_frame, playlist_name, source_name, actions=actions)

    row = 0
    row = controller._add_info_section(content_frame, "General", row)
    row = controller._add_info_row(content_frame, row, "Name", playlist_name)
    row = controller._add_info_row(content_frame, row, "Source", source_name)
    row = controller._add_info_row(content_frame, row, "Playlist ID", playlist_id)
    row = controller._add_info_row(content_frame, row, "Storage Key", playlist_key)
    row = controller._add_info_row(
        content_frame,
        row,
        "Playlist Link",
        playlist_url or "Unavailable",
        action=("Open", lambda: controller._open_external_url(playlist_url)) if playlist_url else None,
    )

    row = controller._add_info_section(content_frame, "Cached Data", row)
    row = controller._add_info_row(content_frame, row, "Saved Item IDs", len(videos))
    row = controller._add_info_row(content_frame, row, "Cached Tracks", len(tracks))
    row = controller._add_info_row(content_frame, row, "Unique Cached Tracks", controller._cached_track_id_count(tracks))
    row = controller._add_info_row(content_frame, row, "Metadata Cached", "Yes" if tracks else "No")

    if tracks:
        first_track = tracks[0]
        last_track = tracks[-1]
        row = controller._add_info_section(content_frame, "Track Snapshot", row)
        row = controller._add_info_row(
            content_frame,
            row,
            "First Track",
            f"{first_track.get('title', 'Unknown Title')} - {first_track.get('artist', 'Unknown Artist')}",
        )
        row = controller._add_info_row(
            content_frame,
            row,
            "Last Track",
            f"{last_track.get('title', 'Unknown Title')} - {last_track.get('artist', 'Unknown Artist')}",
        )

    removed = controller.removed_songs.for_playlist(playlist_key)
    if removed:
        row = controller._add_info_section(content_frame, f"Removed Songs ({len(removed)})", row)
        for song in sorted(removed, key=lambda s: s.get("removed_at", 0), reverse=True):
            when = text_utils.format_relative_age(song["removed_at"]) if song.get("removed_at") else "unknown"
            row = controller._add_info_row(
                content_frame,
                row,
                "Removed",
                f'{song.get("title", "Unknown Title")} — {song.get("artist", "Unknown Artist")} · {when}',
            )
