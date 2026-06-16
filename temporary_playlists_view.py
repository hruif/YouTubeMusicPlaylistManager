"""Temporary Playlists view: the Settings -> Temporary Playlists list and its
per-playlist details window.

Tk view builders extracted from the UI controller (step 2 of decomposing ui.py).
They take the controller as an explicit dependency and call back into it for the
shared info-window toolkit, the YouTube account, source logos, and navigation.
"""
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont

import text_utils


def build(controller, parent):
    controller.current_display_view = "temporary_playlists"
    parent.columnconfigure(0, weight=1)
    parent.rowconfigure(2, weight=1)

    title = ttk.Label(parent, text="Temporary Playlists", font=("Helvetica", 15, "bold"))
    title.grid(row=0, column=0, sticky=tk.W, pady=(0, 8))

    records = controller.youtube_account.load_temporary_playlists()
    description = ttk.Label(
        parent,
        text=(
            "Private playlists created by the queue feature. The timestamp shows how "
            "out of date a queue is, and 'Merged from' lists the playlists it was built "
            "from. Double-click a row for full details and a link to open it on the web. "
            "Delete them when you no longer need them."
        ),
        wraplength=760,
        justify=tk.LEFT,
    )
    description.grid(row=1, column=0, sticky=tk.W, pady=(0, 10))

    if not records:
        empty_label = ttk.Label(parent, text="There are no temporary playlists right now.")
        empty_label.grid(row=2, column=0, sticky=(tk.W, tk.N), pady=(4, 0))
        back_button = ttk.Button(parent, text="Back to Settings", command=controller.show_settings_display)
        back_button.grid(row=3, column=0, sticky=tk.W, pady=(12, 0))
        return

    tree_frame = ttk.Frame(parent)
    tree_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)

    columns = ("title", "created", "age", "sources")
    tree = ttk.Treeview(
        tree_frame,
        columns=columns,
        show="tree headings",
        selectmode="extended",
        style="SourceLogo.Treeview",
    )
    tree.heading("#0", text="")
    tree.heading("title", text="Playlist")
    tree.heading("created", text="Created")
    tree.heading("age", text="Age")
    tree.heading("sources", text="Merged from")
    # Only "Merged from" stretches; the fixed-width columns on the left don't grow into
    # empty space, so widening the window reveals more of the merged-source list instead.
    tree.column("#0", width=38, minwidth=38, stretch=False, anchor=tk.CENTER)
    tree.column("title", width=220, minwidth=140, stretch=False, anchor=tk.W)
    tree.column("created", width=130, minwidth=110, stretch=False, anchor=tk.W)
    tree.column("age", width=110, minwidth=90, stretch=False, anchor=tk.W)
    tree.column("sources", width=260, minwidth=120, stretch=True, anchor=tk.W)
    tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    tree.configure(yscrollcommand=scrollbar.set)

    for record in records:
        kinds = text_utils.temp_playlist_source_kinds(record) or {"youtube"}
        tree.insert(
            "",
            tk.END,
            iid=record.playlist_id,
            image=controller._source_logo_for_sources(kinds),
            values=(
                record.title,
                text_utils.format_timestamp(record.created_at),
                text_utils.format_relative_age(record.created_at),
                text_utils.temp_playlist_source_names(record) or "—",
            ),
        )

    records_by_id = {record.playlist_id: record for record in records}

    # Truncate the (potentially long) "Merged from" text with an ellipsis to the column's
    # current width, and re-fit it whenever the tree is resized or a column is dragged, so
    # the list never spills off-screen and widening the window reveals more.
    sources_font = tkfont.nametofont("TkDefaultFont")
    fixed_source_cols = ("#0", "title", "created", "age")

    def refresh_sources_ellipsis(_event=None):
        tree_width = tree.winfo_width()
        if tree_width <= 1:
            return
        fixed = sum(int(tree.column(col, "width")) for col in fixed_source_cols)
        available = max(40, tree_width - fixed - 8)
        for item_id, record in records_by_id.items():
            full_text = text_utils.temp_playlist_source_names(record) or "—"
            tree.set(item_id, "sources", text_utils.fit_text_to_pixels(full_text, sources_font, available))

    tree.bind("<Configure>", refresh_sources_ellipsis)
    tree.bind("<ButtonRelease-1>", refresh_sources_ellipsis, add="+")
    controller.root.after(0, refresh_sources_ellipsis)

    def selected_records():
        return [records_by_id[item] for item in tree.selection() if item in records_by_id]

    def open_selected():
        chosen = selected_records()
        if not chosen:
            messagebox.showinfo("Temporary Playlists", "Select a playlist first.")
            return
        for record in chosen:
            controller.youtube_account.open_playlist(record.playlist_id)

    def delete_selected():
        chosen = selected_records()
        if not chosen:
            messagebox.showinfo("Temporary Playlists", "Select a playlist to delete first.")
            return
        should_delete = messagebox.askyesno(
            "Delete Temporary Playlists",
            (
                f"Delete {len(chosen)} selected temporary playlist"
                f"{'' if len(chosen) == 1 else 's'} from your account?"
            ),
        )
        if should_delete:
            controller.delete_temporary_youtube_playlists(prompt=False, records=chosen)

    def open_details(event):
        item = tree.identify_row(event.y)
        if item in records_by_id:
            show_details(controller, records_by_id[item])

    tree.bind("<Double-1>", open_details)

    actions = ttk.Frame(parent)
    actions.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(12, 0))

    back_button = ttk.Button(actions, text="Back to Settings", command=controller.show_settings_display)
    back_button.grid(row=0, column=0, sticky=tk.W)

    right_actions = ttk.Frame(actions)
    right_actions.grid(row=0, column=1, sticky=tk.E)
    actions.columnconfigure(1, weight=1)

    open_button = ttk.Button(right_actions, text="Open Selected", command=open_selected)
    open_button.grid(row=0, column=0, padx=(0, 6))
    delete_button = ttk.Button(right_actions, text="Delete Selected", command=delete_selected)
    delete_button.grid(row=0, column=1, padx=(0, 6))
    delete_all_button = ttk.Button(
        right_actions,
        text="Delete All",
        command=controller.delete_temporary_youtube_playlists,
    )
    delete_all_button.grid(row=0, column=2)


def show_details(controller, record):
    details_window, outer_frame, content_frame = controller._create_info_window(
        "Temporary Playlist Info", geometry="720x500"
    )
    content_frame.columnconfigure(1, weight=1)

    playlist_url = (
        controller.youtube_account.playlist_url(record.playlist_id) if record.playlist_id else ""
    )

    actions = []
    if playlist_url:
        actions.append(("Open in Browser", lambda: controller._open_external_url(playlist_url)))
    actions.append(("Close", details_window.destroy))
    controller._add_info_header(
        outer_frame,
        record.title or "Untitled Temporary Playlist",
        f"Created {text_utils.format_timestamp(record.created_at)} "
        f"({text_utils.format_relative_age(record.created_at)})",
        actions=actions,
    )

    row = 0
    row = controller._add_info_section(content_frame, "General", row)
    row = controller._add_info_row(content_frame, row, "Title", record.title or "Untitled")
    row = controller._add_info_row(
        content_frame, row, "Created", text_utils.format_timestamp(record.created_at)
    )
    row = controller._add_info_row(content_frame, row, "Age", text_utils.format_relative_age(record.created_at))
    row = controller._add_info_row(content_frame, row, "Playlist ID", record.playlist_id or "Unknown")
    row = controller._add_info_row(
        content_frame,
        row,
        "Playlist Link",
        playlist_url or "Unavailable",
        action=("Open", lambda: controller._open_external_url(playlist_url)) if playlist_url else None,
    )

    row = controller._add_info_section(content_frame, "Merged from", row)
    sources = record.source_playlists or []
    if not sources:
        row = controller._add_info_row(content_frame, row, "Sources", "Unknown")
    for source in sources:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name") or "Unnamed Playlist")
        source_kind = str(source.get("source") or "").strip().lower()
        source_label = controller._source_name(source_kind) if source_kind else "Source"
        source_id = str(source.get("id") or "")
        source_url = controller._playlist_url(source_kind, source_id) if source_id else ""
        source_logo = (
            controller._source_logo_image(source_kind, size="sidebar")
            if source_kind in ("youtube", "spotify")
            else None
        )
        row = controller._add_info_row(
            content_frame,
            row,
            source_label,
            name,
            action=(
                ("Open", lambda link=source_url: controller._open_external_url(link))
                if source_url
                else None
            ),
            label_image=source_logo,
        )
