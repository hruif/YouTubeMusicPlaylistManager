import re
import tkinter as tk
from tkinter import ttk, messagebox

import playlist_store


class PlaylistURLWindow:
    """Dialog for importing a playlist URL into the main app."""

    def __init__(self, parent, ytmusic, saved_playlists, parent_ui, source='auto'):
        self.source = source
        self.window = tk.Toplevel(parent)
        self.window.title(self._window_title())
        self.window.geometry("500x220")
        self.ytmusic = ytmusic
        self.saved_playlists = saved_playlists
        self.parent_ui = parent_ui

        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        title = ttk.Label(main_frame, text=self._title_text(), font=("Helvetica", 12, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)

        url_label = ttk.Label(main_frame, text="Playlist URL:")
        url_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))

        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        self.url_entry.bind("<Return>", lambda _event: self.on_submit())

        submit_button = ttk.Button(main_frame, text="Add Playlist", command=self.on_submit)
        submit_button.grid(row=3, column=0, columnspan=2, pady=10)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def on_submit(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input", "Please enter a playlist URL")
            return

        source = self._detect_source(url)
        if not source:
            messagebox.showerror("Error", "Paste a YouTube Music or Spotify playlist URL.")
            return

        if source == 'youtube' and not self.ytmusic:
            messagebox.showerror("Error", "YTMusic not initialized")
            return

        if source == 'spotify' and not self.parent_ui.spotapi_available:
            messagebox.showerror(
                "Error",
                "Spotify support is not available. Install spotapi (pip install spotapi) to enable adding public Spotify playlists."
            )
            return

        try:
            playlist_id = self._extract_playlist_id(url, source=source)
            if not playlist_id:
                messagebox.showerror("Error", "Invalid playlist URL format")
                return

            # Fetching remains on the parent so this window stays a thin input dialog.
            if source == 'youtube':
                playlist_entry = self.parent_ui._fetch_youtube_playlist_entry(playlist_id)
            else:
                playlist_entry = self.parent_ui._fetch_spotify_playlist_entry(playlist_id)

            playlist_name = playlist_entry['name']
            saved_count = len(playlist_entry['videos'])
            store_key = playlist_store.playlist_storage_key(source, playlist_id)
            self.saved_playlists[store_key] = playlist_entry
            self.parent_ui.save_playlists()
            self.parent_ui.refresh_playlist_selectors(
                selected_keys=set(self.parent_ui.saved_playlists.keys())
            )
            self.parent_ui._refresh_live_combined_if_active()

            messagebox.showinfo("Success", f"Added playlist: {playlist_name}\n({saved_count} songs)")
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add playlist: {e}")

    def _window_title(self):
        if self.source == 'spotify':
            return "Add Spotify Playlist URL"
        if self.source == 'youtube':
            return "Add YouTube Playlist URL"
        return "Add Playlist URL"

    def _title_text(self):
        if self.source == 'spotify':
            return "Paste Spotify Playlist URL"
        if self.source == 'youtube':
            return "Paste YouTube Playlist URL"
        return "Paste YouTube Music or Spotify Playlist URL"

    def _detect_source(self, url):
        normalized = str(url or '').strip().lower()
        if 'spotify.com/' in normalized or normalized.startswith('spotify:'):
            return 'spotify'
        if 'youtube.com/' in normalized or 'youtu.be/' in normalized:
            return 'youtube'
        if self.source in {'youtube', 'spotify'}:
            return self.source
        return None

    def _extract_playlist_id(self, url, source=None):
        source = source or self._detect_source(url)
        if source == 'spotify':
            return self._extract_spotify_playlist_id(url)
        if source == 'youtube':
            return self._extract_youtube_playlist_id(url)
        return None

    def _extract_youtube_playlist_id(self, url):
        patterns = [
            r'list=([a-zA-Z0-9_-]+)',
            r'playlist/([a-zA-Z0-9_-]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        if len(url) > 20 and '/' not in url:
            return url

        return None

    def _extract_spotify_playlist_id(self, url):
        patterns = [
            r'playlist/([A-Za-z0-9]+)',
            r'spotify:playlist:([A-Za-z0-9]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        if len(url) == 22 and re.fullmatch(r'[A-Za-z0-9]+', url):
            return url

        return None
