"""Reusable playlist checkbox selector: the scrollable list of playlists with a
source badge and a "(N songs)" checkbox per row.

Shared widget extracted from the UI controller (step 2 of decomposing ui.py);
used by both the sidebar and the separate-windows playlist-selection display.
Returns a list of (playlist_key, BooleanVar) pairs.
"""
import tkinter as tk
from tkinter import ttk


def _subtle_highlight(widget, base_color):
    """Return a faint, theme-aware variant of base_color: a touch lighter in dark mode, a
    touch darker in light mode. Falls back to base_color (no tint) if the color can't be read.
    The text color is left at the theme default, so it stays readable on either."""
    try:
        r, g, b = (channel // 256 for channel in widget.winfo_rgb(base_color))
    except tk.TclError:
        return base_color
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    delta = 18 if luminance < 128 else -14
    r = max(0, min(255, r + delta))
    g = max(0, min(255, g + delta))
    b = max(0, min(255, b + delta))
    return f"#{r:02x}{g:02x}{b:02x}"


def build(controller, parent, on_change=None, selected_keys=None, highlight_selected=False, labels_out=None):
    # labels_out (optional dict) is filled with {playlist_key: text-widget} so callers can
    # update a single row's "(N songs)" label in place instead of rebuilding the whole list.
    list_frame = ttk.Frame(parent)
    list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    canvas = tk.Canvas(list_frame, borderwidth=0, highlightthickness=0)
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
    checkbox_frame = ttk.Frame(canvas)

    checkbox_window = canvas.create_window((0, 0), window=checkbox_frame, anchor=tk.NW)

    def on_yscroll(first, last):
        # Auto-hide the scrollbar (and its trough) when everything fits.
        if float(first) <= 0.0 and float(last) >= 1.0:
            scrollbar.grid_remove()
        else:
            scrollbar.grid()
        scrollbar.set(first, last)

    canvas.configure(yscrollcommand=on_yscroll)

    def update_scroll_region(_event=None):
        bbox = canvas.bbox("all")
        if bbox:
            # Pin the top-left to (0, 0) so the list can't be scrolled above its first row.
            canvas.configure(scrollregion=(0, 0, bbox[2], bbox[3]))

    def update_checkbox_width(event):
        canvas.itemconfigure(checkbox_window, width=event.width)

    def on_mousewheel(event):
        # Don't scroll (or "float" the content) when everything already fits.
        first, last = canvas.yview()
        if first <= 0.0 and last >= 1.0:
            return "break"
        if getattr(event, "num", None) == 4:
            scroll_units = -3
        elif getattr(event, "num", None) == 5:
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

    # Theme-aware so it works in both light and dark mode; the ✓ is the primary cue.
    normal_bg = canvas.cget("bg")
    selected_bg = _subtle_highlight(canvas, normal_bg)

    playlist_vars = []
    for row_index, (playlist_key, pl_data) in enumerate(controller._sorted_playlist_items()):
        source = pl_data.get("source", "youtube")
        playlist_name = pl_data.get("name", f"Playlist {playlist_key}")
        song_count = len(pl_data.get("tracks") or pl_data.get("videos", set()))
        selected_var = tk.BooleanVar(value=selected_keys is None or playlist_key in selected_keys)
        playlist_vars.append((playlist_key, selected_var))
        checkbox_frame.columnconfigure(0, weight=1)

        if not highlight_selected:
            # Default rows (sidebar): standard ttk checkbutton, click the box or the name.
            row_frame = ttk.Frame(checkbox_frame, padding=(0, 1))
            row_frame.grid(row=row_index, column=0, sticky=(tk.W, tk.E))
            row_frame.columnconfigure(1, weight=1)

            badge = controller._create_source_badge(row_frame, source)
            badge.grid(row=0, column=0, padx=(0, 5), sticky=tk.W)

            checkbutton = ttk.Checkbutton(
                row_frame,
                text=f"{playlist_name} ({song_count} songs)",
                variable=selected_var,
                command=on_change,
            )
            checkbutton.grid(row=0, column=1, sticky=tk.W)
            if labels_out is not None:
                labels_out[playlist_key] = checkbutton
            for widget in (row_frame, badge, checkbutton):
                bind_mousewheel(widget)
            continue

        # Highlighted, fully-clickable rows (separate-windows picker): the whole row toggles
        # selection, selected rows get a highlight background, and a check mark marks selection.
        logo = controller._source_logo_image(source, size="sidebar")
        row_frame = tk.Frame(checkbox_frame, padx=6, pady=3)
        row_frame.grid(row=row_index, column=0, sticky=(tk.W, tk.E))
        row_frame.columnconfigure(2, weight=1)

        check_label = tk.Label(row_frame, width=2)
        check_label.grid(row=0, column=0, sticky=tk.W)
        badge = tk.Label(row_frame, image=logo)
        badge.image = logo  # keep a reference so the image isn't garbage-collected
        badge.grid(row=0, column=1, padx=(0, 6), sticky=tk.W)
        name_label = tk.Label(row_frame, text=f"{playlist_name} ({song_count} songs)", anchor=tk.W)
        name_label.grid(row=0, column=2, sticky=(tk.W, tk.E))
        if labels_out is not None:
            labels_out[playlist_key] = name_label

        row_widgets = (row_frame, check_label, badge, name_label)

        def make_updater(var, widgets, mark):
            def update(*_args):
                on = var.get()
                bg = selected_bg if on else normal_bg
                for widget in widgets:
                    widget.configure(bg=bg)
                mark.configure(text="✓" if on else "")
            return update

        update_row = make_updater(selected_var, row_widgets, check_label)
        update_row()
        # Trace so Select All / Clear (which set the vars directly) also restyle the row.
        selected_var.trace_add("write", update_row)

        def make_toggle(var):
            def toggle(_event=None):
                var.set(not var.get())
                if on_change:
                    on_change()
                return "break"
            return toggle

        toggle = make_toggle(selected_var)
        for widget in row_widgets:
            widget.bind("<Button-1>", toggle)
            bind_mousewheel(widget)

    return playlist_vars
