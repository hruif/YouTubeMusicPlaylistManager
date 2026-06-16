"""Search Results view: the sidebar-search results screen (a text list of matching
songs with an in-view find/highlight box).

Tk view builder extracted from the UI controller (step 2 of decomposing ui.py).
"""
import tkinter as tk
from tkinter import ttk


def build(controller, parent, query, sorted_results):
    controller.current_display_view = "search"
    controller._active_combined_refresh = None
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
    find_label, find_entry = controller._create_display_find_controls(find_frame, display_find_var)
    find_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
    find_entry.grid(row=0, column=1, sticky=tk.W)

    results_text = tk.Text(parent, height=18, width=90, state=tk.NORMAL)
    results_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    results_text.tag_configure("display_find_match", background="#fff2a8")

    if not sorted_results:
        results_text.insert(
            tk.END,
            f"No songs matching '{query}' were found in your saved playlists.\n\n"
            "Try a different query or add more playlists.",
        )
    else:
        for i, entry in enumerate(sorted_results, 1):
            track = entry["track"]
            in_playlists = sorted(entry["playlists"])
            title = track.get("title", "Unknown")
            artist = track.get("artist", "Unknown")

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
