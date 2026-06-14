import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from ytmusicapi import YTMusic

try:
    from spotapi import PublicPlaylist
    SPOTAPI_AVAILABLE = True
except ImportError:
    PublicPlaylist = None
    SPOTAPI_AVAILABLE = False


class PlaylistManagerUI:
    PLAYLIST_FILE = Path(__file__).with_name("saved_playlists.json")
    ASSETS_DIR = Path(__file__).with_name("assets")
    SOURCE_LABELS = {
        'youtube': 'YouTube',
        'spotify': 'Spotify'
    }
    COMBINED_SORT_OPTIONS = {
        'Title (A-Z)': 'title',
        'Artist (A-Z)': 'artist',
        'Playlist Name': 'playlist',
        'Source': 'source',
        'Original Playlist Order': 'original'
    }

    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Music Public Playlist Manager")
        self.root.geometry("900x620")
        self.root.minsize(860, 580)
        
        # Initialize YTMusic (no authentication needed for public playlists)
        try:
            self.ytmusic = YTMusic()
            print("YTMusic initialized for public playlist access")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize YTMusic: {e}")
            self.ytmusic = None

        # Initialize SpotAPI support (for Spotify-like imports)
        self.spotapi_available = SPOTAPI_AVAILABLE
        
        # Store saved playlists
        self.saved_playlists = {}  # {source:playlist_id: {source, id, name, videos, tracks}}
        self.playlists_file = self.PLAYLIST_FILE
        
        # Load saved playlists on startup
        self.load_playlists()
        
        # Show loaded playlists count
        if self.saved_playlists:
            print(f"Loaded {len(self.saved_playlists)} saved playlists")
            # Could add a status label here if desired

        self.use_display_windows_var = tk.BooleanVar(value=False)
        self.source_logo_images = self._build_source_logo_images()
        self.sidebar_playlist_vars = []
        self.display_playlist_vars = []
        self.current_display_view = 'empty'
        self.style = ttk.Style()
        self.style.configure("SourceLogo.Treeview", rowheight=32)
        
        self.main_frame = ttk.Frame(root, padding="14")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.sidebar_frame = ttk.Frame(self.main_frame, width=270)
        self.sidebar_frame.grid(row=0, column=0, sticky=(tk.W, tk.N, tk.S), padx=(0, 14))
        self.sidebar_frame.grid_propagate(False)

        self.display_frame = ttk.Frame(self.main_frame)
        self.display_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))

        title = ttk.Label(self.sidebar_frame, text="Playlist Manager", font=("Helvetica", 15, "bold"))
        title.grid(row=0, column=0, sticky=tk.W, pady=(0, 14))

        search_label = ttk.Label(self.sidebar_frame, text="Search songs:")
        search_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))

        self.search_entry = ttk.Entry(self.sidebar_frame)
        self.search_entry.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        self.root.bind_all("<Control-f>", self._focus_sidebar_search)
        self.root.bind_all("<Command-f>", self._focus_sidebar_search)

        button_frame = ttk.Frame(self.sidebar_frame)
        button_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        button_frame.columnconfigure(0, weight=1)

        search_button = ttk.Button(button_frame, text="Search", command=self.on_search)
        search_button.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)

        add_playlist_button = ttk.Button(button_frame, text="Add YouTube Playlist URL", command=self.open_playlist_window)
        add_playlist_button.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)

        add_spotify_button = ttk.Button(button_frame, text="Add Spotify Playlist URL", command=self.open_spotify_playlist_window)
        add_spotify_button.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)

        view_playlists_button = ttk.Button(button_frame, text="View Saved Playlists", command=self.view_saved_playlists)
        view_playlists_button.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=2)

        find_duplicates_button = ttk.Button(button_frame, text="Find Duplicates in Selection", command=self.find_duplicate_songs)
        find_duplicates_button.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=2)

        update_selected_button = ttk.Button(button_frame, text="Update Selected Playlists", command=self.update_selected_playlists)
        update_selected_button.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=2)

        combined_songs_button = ttk.Button(button_frame, text="View Combined Songs", command=self.open_combined_songs_selector)
        combined_songs_button.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=2)

        settings_button = ttk.Button(button_frame, text="Settings", command=self.show_settings_display)
        settings_button.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(12, 2))

        self.playlist_selector_container = ttk.LabelFrame(self.sidebar_frame, text="Playlists", padding=(6, 4))
        self.playlist_selector_container.grid(row=5, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.sidebar_selection_actions = ttk.Frame(self.sidebar_frame)
        self.sidebar_selection_actions.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=(8, 0))
        self.sidebar_selection_actions.columnconfigure(0, weight=1)
        self.sidebar_selection_actions.columnconfigure(1, weight=1)

        select_all_button = ttk.Button(self.sidebar_selection_actions, text="Select All", command=lambda: self._set_playlist_selection(self._active_playlist_vars(), True))
        select_all_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 4))

        clear_button = ttk.Button(self.sidebar_selection_actions, text="Clear", command=lambda: self._set_playlist_selection(self._active_playlist_vars(), False))
        clear_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(4, 0))

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.sidebar_frame.columnconfigure(0, weight=1)
        self.sidebar_frame.rowconfigure(5, weight=1)
        self.display_frame.columnconfigure(0, weight=1)
        self.display_frame.rowconfigure(1, weight=1)
        self.refresh_sidebar_playlists()
        self.show_empty_display()
    
    def load_playlists(self):
        """Load saved playlists from file"""
        try:
            if not self.playlists_file.exists():
                print("No saved playlists file found, starting fresh")
                self.saved_playlists = {}
                return

            with self.playlists_file.open('r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, dict):
                print("Invalid playlist data format, starting fresh")
                self.saved_playlists = {}
                return

            self.saved_playlists = {}
            migrated = False
            for stored_key, pl_data in data.items():
                entry = self._normalize_playlist_entry(stored_key, pl_data)
                if not entry:
                    migrated = True
                    continue

                store_key = self._playlist_storage_key(entry['source'], entry['id'])
                self.saved_playlists[store_key] = entry
                if store_key != stored_key or not self._is_current_playlist_format(pl_data):
                    migrated = True

            print(f"Loaded {len(self.saved_playlists)} playlists from {self.playlists_file}")

            if migrated:
                print("Migrating playlist data to the current format...")
                self.save_playlists()
                print("Migration complete.")
        except json.JSONDecodeError as e:
            print(f"Corrupted playlist file: {e}, starting fresh")
            self.saved_playlists = {}
            # Backup the corrupted file
            if self.playlists_file.exists():
                backup_file = self._playlists_backup_file()
                self.playlists_file.replace(backup_file)
                print(f"Backed up corrupted file to {backup_file}")
        except Exception as e:
            print(f"Error loading playlists: {e}")
            self.saved_playlists = {}

    # SpotAPI (spotapi.PublicPlaylist) is used for public Spotify playlist access.
    # No client credentials are required for public playlist fetching via SpotAPI.

    def _playlists_backup_file(self):
        return self.playlists_file.with_name(f"{self.playlists_file.name}.backup")

    def _playlists_temp_file(self):
        return self.playlists_file.with_name(f"{self.playlists_file.name}.tmp")

    def _playlist_storage_key(self, source, playlist_id):
        return f"{source}:{playlist_id}"

    def _split_storage_key(self, stored_key):
        if isinstance(stored_key, str) and ':' in stored_key:
            source, playlist_id = stored_key.split(':', 1)
            if source in self.SOURCE_LABELS and playlist_id:
                return source, playlist_id
        return 'youtube', stored_key

    def _normalize_playlist_identity(self, stored_key, pl_data):
        stored_source, stored_playlist_id = self._split_storage_key(stored_key)

        source = pl_data.get('source') or stored_source
        if source not in self.SOURCE_LABELS:
            source = stored_source

        playlist_id = pl_data.get('id') or stored_playlist_id
        if isinstance(playlist_id, str) and playlist_id.startswith(f"{source}:"):
            playlist_id = playlist_id.split(':', 1)[1]

        return source, playlist_id

    def _normalize_playlist_entry(self, stored_key, pl_data):
        if not isinstance(pl_data, dict):
            return None

        source, playlist_id = self._normalize_playlist_identity(stored_key, pl_data)
        if not playlist_id:
            return None

        tracks = self._normalize_tracks(source, pl_data.get('tracks', []))
        videos = self._coerce_id_set(pl_data.get('videos'))
        if not videos:
            videos = self._coerce_id_set(track.get('id') for track in tracks)

        if not tracks and videos and source == 'youtube':
            tracks = self._load_youtube_tracks_for_legacy_playlist(playlist_id, videos)

        return self._build_playlist_entry(
            source=source,
            playlist_id=playlist_id,
            playlist_name=pl_data.get('name', 'Unnamed Playlist'),
            item_ids=videos,
            tracks=tracks
        )

    def _is_current_playlist_format(self, pl_data):
        return (
            isinstance(pl_data, dict)
            and 'source' in pl_data
            and 'id' in pl_data
            and 'tracks' in pl_data
            and isinstance(pl_data.get('videos'), list)
        )

    def _coerce_id_set(self, values):
        if values is None:
            return set()
        if isinstance(values, set):
            return {value for value in values if value}
        if isinstance(values, (list, tuple)):
            return {value for value in values if value}
        if not isinstance(values, str):
            try:
                return {value for value in values if value}
            except TypeError:
                return set()
        return {values} if values else set()

    def _normalize_tracks(self, source, tracks):
        if not isinstance(tracks, list):
            return []

        normalized_tracks = []
        for track in tracks:
            if not isinstance(track, dict):
                continue

            normalized = dict(track)
            track_id = normalized.get('id') or normalized.get('trackId') or normalized.get('videoId')
            if not track_id:
                continue
            track_id = str(track_id)
            if source == 'spotify' and track_id.startswith('spotify:track:'):
                track_id = track_id.rsplit(':', 1)[1]

            normalized['id'] = track_id
            normalized['source'] = source
            if source == 'youtube':
                normalized['videoId'] = normalized.get('videoId') or track_id
            elif source == 'spotify':
                normalized['trackId'] = normalized.get('trackId') or track_id

            normalized.setdefault('title', 'Unknown Title')
            normalized.setdefault('artist', 'Unknown Artist')
            normalized_tracks.append(normalized)

        return normalized_tracks

    def _load_youtube_tracks_for_legacy_playlist(self, playlist_id, video_ids):
        if not self.ytmusic:
            return self._fallback_youtube_tracks(video_ids)

        try:
            playlist_data = self.ytmusic.get_playlist(playlist_id, limit=500)
            _, tracks = self._extract_track_metadata(playlist_data)
            return [track for track in tracks if track.get('videoId') in video_ids]
        except Exception as e:
            print(f"Could not fetch metadata for playlist {playlist_id}: {e}")
            return self._fallback_youtube_tracks(video_ids)

    def _fallback_youtube_tracks(self, video_ids):
        return [
            {
                'id': video_id,
                'videoId': video_id,
                'title': f'Song ID: {video_id}',
                'artist': 'Unknown Artist',
                'source': 'youtube'
            }
            for video_id in sorted(video_ids)
        ]

    def _build_playlist_entry(self, source, playlist_id, playlist_name, item_ids, tracks):
        return {
            'source': source,
            'id': playlist_id,
            'name': playlist_name or 'Unnamed Playlist',
            'videos': set(item_ids),
            'tracks': tracks
        }

    def _serialize_playlist_entry(self, playlist_key, pl_data):
        source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
        return {
            'source': source,
            'id': playlist_id,
            'name': pl_data.get('name', 'Unnamed Playlist'),
            'videos': sorted(self._coerce_id_set(pl_data.get('videos'))),
            'tracks': self._normalize_tracks(source, pl_data.get('tracks', []))
        }

    def save_playlists(self):
        """Save playlists to file"""
        try:
            json_data = {}
            for playlist_key, pl_data in self.saved_playlists.items():
                source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
                store_key = self._playlist_storage_key(source, playlist_id)
                json_data[store_key] = self._serialize_playlist_entry(playlist_key, pl_data)

            temp_file = self._playlists_temp_file()
            with temp_file.open('w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            if self.playlists_file.exists():
                self.playlists_file.replace(self._playlists_backup_file())

            temp_file.replace(self.playlists_file)
            print(f"Saved {len(self.saved_playlists)} playlists to {self.playlists_file}")
        except Exception as e:
            print(f"Error saving playlists: {e}")
            messagebox.showerror("Error", f"Failed to save playlists: {e}")
            # Try to restore backup
            backup_file = self._playlists_backup_file()
            if backup_file.exists():
                backup_file.replace(self.playlists_file)
                print("Restored backup file")
    
    def _extract_playlist_name(self, playlist, fallback_name='Unnamed Playlist'):
        playlist_name = self._extract_text_value(playlist.get('title'))
        if playlist_name:
            return playlist_name

        header = playlist.get('header')
        playlist_name = None
        if isinstance(header, dict):
            playlist_name = self._extract_text_value(header.get('title'))
        if playlist_name:
            return playlist_name

        if isinstance(header, dict):
            renderer = (
                header.get('musicDetailHeaderRenderer')
                or header.get('musicResponsiveHeaderRenderer')
            )
            if isinstance(renderer, dict):
                playlist_name = self._extract_text_value(renderer.get('title'))
                if playlist_name:
                    return playlist_name

        return fallback_name

    def _extract_text_value(self, value):
        if isinstance(value, str):
            return value
        if not isinstance(value, dict):
            return None

        if isinstance(value.get('text'), str):
            return value['text']

        runs = value.get('runs')
        if isinstance(runs, list) and runs:
            first_run = runs[0]
            if isinstance(first_run, dict) and isinstance(first_run.get('text'), str):
                return first_run['text']

        return None

    def _extract_track_metadata(self, playlist):
        tracks_data = []
        video_ids = set()

        for track in playlist.get('tracks', []):
            if 'videoId' not in track:
                continue

            video_id = track['videoId']
            video_ids.add(video_id)

            title = track.get('title', 'Unknown Title')
            artist = self._extract_youtube_artist(track.get('artists', []))

            tracks_data.append({
                'id': video_id,
                'videoId': video_id,
                'title': title,
                'artist': artist,
                'source': 'youtube'
            })

        return video_ids, tracks_data

    def _extract_youtube_artist(self, artists):
        if isinstance(artists, list) and artists:
            first_artist = artists[0]
            if isinstance(first_artist, dict):
                return first_artist.get('name') or 'Unknown Artist'
            return str(first_artist)
        return 'Unknown Artist'

    def _get_spotify_playlist_name(self, info, fallback_name):
        if not info:
            return fallback_name

        if isinstance(info, dict):
            if info.get('name'):
                return info['name']

            data = info.get('data')
            if isinstance(data, dict):
                playlist_v2 = data.get('playlistV2')
                if isinstance(playlist_v2, dict):
                    if playlist_v2.get('name'):
                        return playlist_v2.get('name')
                    content = playlist_v2.get('content')
                    if isinstance(content, dict) and content.get('name'):
                        return content.get('name')
                if data.get('name'):
                    return data.get('name')
            return fallback_name

        try:
            for inf in info:
                if isinstance(inf, dict):
                    return self._get_spotify_playlist_name(inf, fallback_name)
        except Exception:
            pass

        return fallback_name

    def _extract_spotify_track_from_item(self, item):
        if not isinstance(item, dict):
            return None

        track = None
        if 'track' in item and isinstance(item['track'], dict):
            track = item['track']
        elif 'item' in item and isinstance(item['item'], dict):
            track = item['item'].get('data') or item['item']
        elif 'itemV2' in item and isinstance(item['itemV2'], dict):
            track = item['itemV2'].get('data') or item['itemV2']
        elif 'data' in item and isinstance(item['data'], dict):
            track = item['data']
        else:
            track = item

        if not track or not isinstance(track, dict):
            return None

        track_id = track.get('id') or track.get('trackId') or track.get('uri')
        if not track_id:
            nested = track.get('track') if isinstance(track.get('track'), dict) else None
            if nested:
                track_id = nested.get('id') or nested.get('uri')
                track = nested
        if not track_id:
            return None
        track_id = str(track_id)
        if track_id.startswith('spotify:track:'):
            track_id = track_id.rsplit(':', 1)[1]

        title = track.get('name') or track.get('title') or ''
        artist = self._extract_spotify_artist_name(track.get('artists'))

        return {
            'id': track_id,
            'trackId': track_id,
            'title': title,
            'artist': artist,
            'source': 'spotify'
        }

    def _extract_spotify_artist_name(self, artists):
        if isinstance(artists, list) and artists:
            return self._spotify_artist_name_from_value(artists[0])

        if isinstance(artists, dict):
            artist_items = artists.get('items')
            if isinstance(artist_items, list) and artist_items:
                return self._spotify_artist_name_from_value(artist_items[0])

        return ''

    def _spotify_artist_name_from_value(self, artist):
        if isinstance(artist, dict):
            profile = artist.get('profile')
            profile_name = profile.get('name') if isinstance(profile, dict) else None
            return artist.get('name') or profile_name or ''
        return str(artist) if artist else ''

    def _extract_spotify_items_from_page(self, page):
        if isinstance(page, list):
            return page
        if not isinstance(page, dict):
            return []

        for key in ('items', 'tracks', 'data', 'content', 'contents', 'playlistV2'):
            value = page.get(key)
            if isinstance(value, list):
                return value
            nested_items = self._extract_spotify_items_from_page(value)
            if nested_items:
                return nested_items

        if any(key in page for key in ('track', 'item', 'itemV2', 'id', 'trackId', 'uri')):
            return [page]

        return []

    def _fetch_youtube_playlist_entry(self, playlist_id, fallback_name='Unnamed Playlist'):
        if not self.ytmusic:
            raise RuntimeError("YTMusic is not initialized")

        playlist = self.ytmusic.get_playlist(playlist_id, limit=500)
        playlist_name = self._extract_playlist_name(playlist, fallback_name)
        video_ids, tracks_data = self._extract_track_metadata(playlist)
        return self._build_playlist_entry('youtube', playlist_id, playlist_name, video_ids, tracks_data)

    def _fetch_spotify_playlist_entry(self, playlist_id, fallback_name=None):
        if not self.spotapi_available or PublicPlaylist is None:
            raise RuntimeError("SpotAPI (spotapi) is not available")

        track_ids = set()
        tracks_data = []
        playlist_name = fallback_name or f"Spotify Playlist {playlist_id}"

        pl = PublicPlaylist(playlist_id)
        try:
            info = pl.get_playlist_info()
            playlist_name = self._get_spotify_playlist_name(info, playlist_name)
        except Exception as e:
            print(f"Could not fetch Spotify playlist info for {playlist_id}: {e}")

        for page in pl.paginate_playlist():
            for item in self._extract_spotify_items_from_page(page):
                track = self._extract_spotify_track_from_item(item)
                if not track:
                    continue
                track_ids.add(track['id'])
                tracks_data.append(track)

        if not tracks_data:
            raise RuntimeError("No valid Spotify tracks were found.")

        return self._build_playlist_entry('spotify', playlist_id, playlist_name, track_ids, tracks_data)

    def _normalize_song_key(self, title, artist):
        combined = f"{title or ''} {artist or ''}".lower()
        combined = re.sub(r"[^\w\s]", "", combined)
        combined = re.sub(r"\s+", " ", combined).strip()
        return combined

    def _normalize_search_text(self, text):
        normalized = str(text or '').lower()
        normalized = re.sub(r"[^\w\s]", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _source_name(self, source):
        return self.SOURCE_LABELS.get(source, source.title() if source else 'Unknown')

    def _build_source_logo_images(self):
        return {
            'sidebar': {
                'youtube': self._load_logo_image('youtube_18.png', 18, '#ff0000'),
                'spotify': self._load_logo_image('spotify_18.png', 18, '#1db954')
            },
            'table': {
                'youtube': self._load_logo_image('youtube_24.png', 24, '#ff0000'),
                'spotify': self._load_logo_image('spotify_24.png', 24, '#1db954'),
                'mixed': self._load_logo_image('mixed_24.png', 24, '#777777')
            }
        }

    def _load_logo_image(self, filename, size, fallback_color):
        logo_path = self.ASSETS_DIR / filename
        if logo_path.exists():
            return tk.PhotoImage(file=str(logo_path))

        image = tk.PhotoImage(width=size, height=size)
        image.put(fallback_color, to=(0, 0, size, size))
        return image

    def _source_logo_image(self, source, size='table'):
        images = self.source_logo_images.get(size, self.source_logo_images['table'])
        return images.get(source, self.source_logo_images['table'].get('mixed'))

    def _source_logo_for_sources(self, sources):
        if len(sources) == 1:
            return self._source_logo_image(next(iter(sources)))
        return self.source_logo_images['table']['mixed']

    def _create_source_badge(self, parent, source):
        return ttk.Label(parent, image=self._source_logo_image(source, size='sidebar'))

    def _focus_widget(self, widget):
        try:
            if widget is not None and widget.winfo_exists():
                widget.focus_set()
                if isinstance(widget, ttk.Entry):
                    widget.selection_range(0, tk.END)
                return "break"
        except tk.TclError:
            pass
        return self._focus_sidebar_search()

    def _focus_sidebar_search(self, _event=None):
        try:
            self.search_entry.focus_set()
            self.search_entry.selection_range(0, tk.END)
        except tk.TclError:
            pass
        return "break"

    def _register_display_find_entry(self, parent, find_entry):
        top_level = parent.winfo_toplevel()

        def focus_find(_event=None):
            return self._focus_widget(find_entry)

        top_level.bind("<Control-f>", focus_find)
        top_level.bind("<Command-f>", focus_find)

    def _create_display_find_controls(self, parent, find_var):
        find_label = ttk.Label(parent, text="Find:")
        find_entry = ttk.Entry(parent, textvariable=find_var, width=24)
        find_entry.bind("<Escape>", lambda _event: (find_var.set(""), "break")[-1])
        self._register_display_find_entry(parent, find_entry)
        return find_label, find_entry

    def _matches_find_query(self, values, query):
        terms = [term for term in self._normalize_search_text(query).split() if term]
        if not terms:
            return True

        haystack = self._normalize_search_text(" ".join(str(value or "") for value in values))
        return all(term in haystack for term in terms)

    def _clear_display_frame(self):
        for child in self.display_frame.winfo_children():
            child.destroy()

    def _open_display_window(self, title, build_display, geometry="900x620"):
        display_window = tk.Toplevel(self.root)
        display_window.title(title)
        display_window.geometry(geometry)

        display_frame = ttk.Frame(display_window, padding="20")
        display_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        display_window.columnconfigure(0, weight=1)
        display_window.rowconfigure(0, weight=1)

        build_display(display_frame)
        return display_window

    def _show_display(self, title, build_display, geometry="900x620"):
        if self.use_display_windows_var.get():
            self._open_display_window(title, build_display, geometry=geometry)
            if self.current_display_view != 'playlist_selection':
                self.show_playlist_selection_display()
            return

        self._clear_display_frame()
        build_display(self.display_frame)

    def _active_playlist_vars(self):
        if self.use_display_windows_var.get() and self.display_playlist_vars:
            return self.display_playlist_vars
        return self.sidebar_playlist_vars

    def _selected_playlist_keys_from_active_display(self):
        return self._selected_playlist_keys(self._active_playlist_vars())

    def _on_display_mode_changed(self):
        selected_keys = set(self._selected_playlist_keys_from_active_display())
        if self.use_display_windows_var.get():
            self.playlist_selector_container.grid_remove()
            self.sidebar_selection_actions.grid_remove()
            self.show_playlist_selection_display(selected_keys=selected_keys)
            return

        self.display_playlist_vars = []
        self.playlist_selector_container.grid()
        self.sidebar_selection_actions.grid()
        self.refresh_sidebar_playlists(selected_keys=selected_keys)
        self.show_empty_display()

    def show_empty_display(self):
        self.current_display_view = 'empty'
        self._active_combined_refresh = None
        self._clear_display_frame()

        empty_frame = ttk.Frame(self.display_frame)
        empty_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        empty_frame.columnconfigure(0, weight=1)
        empty_frame.rowconfigure(0, weight=1)

        empty_label = ttk.Label(empty_frame, text="Choose an action from the sidebar.", font=("Helvetica", 13))
        empty_label.grid(row=0, column=0)

        self.display_frame.columnconfigure(0, weight=1)
        self.display_frame.rowconfigure(0, weight=1)

    def refresh_sidebar_playlists(self, selected_keys=None):
        for child in self.playlist_selector_container.winfo_children():
            child.destroy()

        self.sidebar_playlist_vars = self._build_playlist_checkbox_selector(
            self.playlist_selector_container,
            on_change=self._on_sidebar_playlist_changed,
            selected_keys=selected_keys
        )

    def refresh_playlist_selectors(self, selected_keys=None):
        self.refresh_sidebar_playlists(selected_keys=selected_keys)
        if self.use_display_windows_var.get():
            self.show_playlist_selection_display(selected_keys=selected_keys)

    def _selected_sidebar_playlist_keys(self):
        return self._selected_playlist_keys_from_active_display()

    def _on_sidebar_playlist_changed(self):
        if getattr(self, 'current_display_view', None) == 'combined':
            refresh = getattr(self, '_active_combined_refresh', None)
            if refresh:
                refresh()

    def _refresh_live_combined_if_active(self):
        if getattr(self, 'current_display_view', None) == 'combined':
            refresh = getattr(self, '_active_combined_refresh', None)
            if refresh:
                refresh()

    def show_settings_display(self):
        def build_settings_display(parent):
            self.current_display_view = 'settings'
            parent.columnconfigure(0, weight=1)

            title = ttk.Label(parent, text="Settings", font=("Helvetica", 15, "bold"))
            title.grid(row=0, column=0, sticky=tk.W, pady=(0, 14))

            display_frame = ttk.LabelFrame(parent, text="Display", padding="12")
            display_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
            display_frame.columnconfigure(0, weight=1)

            display_window_setting = ttk.Checkbutton(
                display_frame,
                text="Open display output in separate windows",
                variable=self.use_display_windows_var,
                command=self._on_display_mode_changed
            )
            display_window_setting.grid(row=0, column=0, sticky=tk.W)

            description = ttk.Label(
                display_frame,
                text=(
                    "When enabled, search results, saved playlists, combined songs, "
                    "duplicate results, and settings open in windows. The main display "
                    "is used for playlist selection."
                ),
                wraplength=520
            )
            description.grid(row=1, column=0, sticky=tk.W, pady=(8, 0))

        self._show_display("Settings", build_settings_display, geometry="620x260")

    def _find_matching_tracks(self, query):
        query_terms = [term for term in self._normalize_search_text(query).split() if term]
        if not query_terms:
            return {}

        matches = {}
        for pl_id, pl_data in self.saved_playlists.items():
            playlist_name = pl_data.get('name', f'Playlist {pl_id}')
            source = pl_data.get('source', 'youtube')
            source_label = f"{self._source_name(source)}: {playlist_name}"
            for track in pl_data.get('tracks', []):
                title = track.get('title', '')
                artist = track.get('artist', '')
                searchable_text = self._normalize_search_text(f"{title} {artist}")

                if all(term in searchable_text for term in query_terms):
                    track_key = self._normalize_song_key(title, artist)
                    if not track_key:
                        continue

                    if track_key not in matches:
                        matches[track_key] = {
                            'track': track,
                            'playlists': set()
                        }
                    matches[track_key]['playlists'].add(source_label)

        return matches

    def _playlist_label(self, playlist_key, pl_data):
        return pl_data.get('name', f'Playlist {playlist_key}')

    def _combined_track_key(self, track):
        title = track.get('title', '')
        artist = track.get('artist', '')
        song_key = self._normalize_song_key(title, artist)
        if song_key:
            return song_key

        source = track.get('source', 'youtube')
        track_id = track.get('id') or track.get('trackId') or track.get('videoId')
        if track_id:
            return f"{source}:{track_id}"

        return None

    def _collect_combined_tracks(self, playlist_keys, merge_duplicates=True):
        combined = []
        merged_entries = {}

        for playlist_order, playlist_key in enumerate(playlist_keys):
            pl_data = self.saved_playlists.get(playlist_key)
            if not pl_data:
                continue

            source = pl_data.get('source', 'youtube')
            playlist_label = self._playlist_label(playlist_key, pl_data)
            for track_order, track in enumerate(pl_data.get('tracks', [])):
                if not isinstance(track, dict):
                    continue

                title = track.get('title') or 'Unknown Title'
                artist = track.get('artist') or 'Unknown Artist'
                entry_key = self._combined_track_key(track)
                if not entry_key:
                    entry_key = f"{playlist_key}:{track_order}"

                if not merge_duplicates:
                    entry_key = f"{playlist_key}:{track_order}:{entry_key}"

                if merge_duplicates and entry_key in merged_entries:
                    entry = merged_entries[entry_key]
                    entry['playlists'].add(playlist_label)
                    entry['sources'].add(source)
                    entry['appearance_count'] += 1
                    continue

                entry = {
                    'key': entry_key,
                    'track': track,
                    'title': title,
                    'artist': artist,
                    'playlists': {playlist_label},
                    'sources': {source},
                    'playlist_order': playlist_order,
                    'track_order': track_order,
                    'appearance_count': 1
                }
                combined.append(entry)
                if merge_duplicates:
                    merged_entries[entry_key] = entry

        return combined

    def _sort_combined_tracks(self, tracks, sort_label):
        sort_mode = self.COMBINED_SORT_OPTIONS.get(sort_label, sort_label)

        def normalized(value):
            return self._normalize_search_text(value)

        def playlist_name(entry):
            return normalized(next(iter(sorted(entry['playlists'])), ''))

        def source_name(entry):
            return normalized(next(iter(sorted(entry['sources'])), ''))

        sorters = {
            'title': lambda entry: (
                normalized(entry['title']),
                normalized(entry['artist']),
                entry['playlist_order'],
                entry['track_order']
            ),
            'artist': lambda entry: (
                normalized(entry['artist']),
                normalized(entry['title']),
                entry['playlist_order'],
                entry['track_order']
            ),
            'playlist': lambda entry: (
                playlist_name(entry),
                entry['playlist_order'],
                entry['track_order'],
                normalized(entry['title'])
            ),
            'source': lambda entry: (
                source_name(entry),
                normalized(entry['title']),
                normalized(entry['artist'])
            ),
            'original': lambda entry: (
                entry['playlist_order'],
                entry['track_order'],
                normalized(entry['title'])
            )
        }

        return sorted(tracks, key=sorters.get(sort_mode, sorters['title']))

    def on_search(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Input", "Please enter a song name")
            return
        
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first")
            return

        filtered_results = self._find_matching_tracks(query)
        self.show_search_results_display(query, filtered_results)

    def show_search_results_display(self, query, filtered_results):
        sorted_results = sorted(
            filtered_results.values(),
            key=lambda entry: entry['track'].get('title', '').lower()
        )

        def build_search_display(parent):
            self.current_display_view = 'search'
            self._active_combined_refresh = None
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(1, weight=1)

            header_frame = ttk.Frame(parent)
            header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
            header_frame.columnconfigure(0, weight=1)

            results_label = ttk.Label(header_frame, text=f"Search Results: {query}", font=("Helvetica", 15, "bold"))
            results_label.grid(row=0, column=0, sticky=tk.W)

            display_find_var = tk.StringVar()
            find_label, find_entry = self._create_display_find_controls(header_frame, display_find_var)
            find_label.grid(row=0, column=1, sticky=tk.E, padx=(12, 4))
            find_entry.grid(row=0, column=2, sticky=tk.E)

            results_text = tk.Text(parent, height=18, width=90, state=tk.NORMAL)
            results_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            results_text.tag_configure("display_find_match", background="#fff2a8")

            if not sorted_results:
                results_text.insert(tk.END, f"No songs matching '{query}' were found in your saved playlists.\n\nTry a different query or add more playlists.")
            else:
                for i, entry in enumerate(sorted_results, 1):
                    track = entry['track']
                    in_playlists = sorted(entry['playlists'])
                    title = track.get('title', 'Unknown')
                    artist = track.get('artist', 'Unknown')

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

        self._show_display("Search Results", build_search_display)
    
    def open_playlist_window(self):
        PlaylistURLWindow(self.root, self.ytmusic, self.saved_playlists, self, source='youtube')

    def open_spotify_playlist_window(self):
        if not self.spotapi_available:
            messagebox.showerror(
                "Spotify Not Available",
                "Spotify support is disabled because the spotapi package is not installed.\n\nInstall it with: pip install spotapi"
            )
            return
        PlaylistURLWindow(self.root, self.ytmusic, self.saved_playlists, self, source='spotify')

    def view_saved_playlists(self):
        """Show a window with saved playlists"""
        if not self.saved_playlists:
            messagebox.showinfo("Saved Playlists", "No playlists saved yet.\n\nAdd some playlists using the add playlist buttons.")
            return

        self.show_saved_playlists_display()

    def show_saved_playlists_display(self):
        self._show_display("Saved Playlists", self._build_saved_playlists_display)

    def _build_saved_playlists_display(self, parent):
        self.current_display_view = 'playlists'
        self._active_combined_refresh = None

        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)

        title = ttk.Label(header_frame, text=f"Saved Playlists ({len(self.saved_playlists)})", font=("Helvetica", 15, "bold"))
        title.grid(row=0, column=0, sticky=tk.W)

        display_find_var = tk.StringVar()
        find_label, find_entry = self._create_display_find_controls(header_frame, display_find_var)
        find_label.grid(row=0, column=1, sticky=tk.E, padx=(12, 4))
        find_entry.grid(row=0, column=2, sticky=tk.E)

        table_frame = ttk.Frame(parent)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        playlists_tree = ttk.Treeview(
            table_frame,
            columns=('name', 'source', 'songs', 'tracks', 'id'),
            show='tree headings',
            style="SourceLogo.Treeview",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )
        playlists_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        y_scrollbar.config(command=playlists_tree.yview)
        x_scrollbar.config(command=playlists_tree.xview)

        playlists_tree.heading('#0', text='')
        playlists_tree.heading('name', text='Playlist')
        playlists_tree.heading('source', text='Source')
        playlists_tree.heading('songs', text='Songs')
        playlists_tree.heading('tracks', text='Cached Tracks')
        playlists_tree.heading('id', text='ID')

        playlists_tree.column('#0', width=38, minwidth=38, stretch=False, anchor=tk.CENTER)
        playlists_tree.column('name', width=260, minwidth=160)
        playlists_tree.column('source', width=120, minwidth=90, stretch=False)
        playlists_tree.column('songs', width=80, minwidth=70, stretch=False, anchor=tk.CENTER)
        playlists_tree.column('tracks', width=110, minwidth=90, stretch=False, anchor=tk.CENTER)
        playlists_tree.column('id', width=260, minwidth=160)

        playlist_rows = []
        for playlist_key, pl_data in self.saved_playlists.items():
            source = pl_data.get('source', 'youtube')
            videos = pl_data.get('videos', set())
            tracks = pl_data.get('tracks', [])
            row_values = (
                pl_data.get('name', 'Unnamed'),
                self._source_name(source),
                len(videos),
                len(tracks),
                pl_data.get('id', playlist_key)
            )
            playlist_rows.append((source, row_values))

        def refresh_playlist_rows(*_):
            for item_id in playlists_tree.get_children():
                playlists_tree.delete(item_id)

            visible_rows = [
                row
                for row in playlist_rows
                if self._matches_find_query(row[1], display_find_var.get())
            ]

            if not visible_rows:
                playlists_tree.insert(
                    '',
                    tk.END,
                    values=('No saved playlists match the current find text.', '', '', '', '')
                )
                return

            for source, row_values in visible_rows:
                playlists_tree.insert(
                    '',
                    tk.END,
                    image=self._source_logo_image(source),
                    values=row_values
                )

        display_find_var.trace_add("write", refresh_playlist_rows)
        refresh_playlist_rows()

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

    def open_combined_songs_selector(self):
        """Show a combined song view for the selected playlists."""
        if not self.saved_playlists:
            messagebox.showinfo("Combined Songs", "No playlists saved yet.\n\nAdd some playlists using the add playlist buttons.")
            return

        selected_keys = self._selected_sidebar_playlist_keys()
        if not selected_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist.")
            return

        self.show_combined_songs_display(selected_keys, live=not self.use_display_windows_var.get())

    def show_playlist_selection_display(self, selected_keys=None):
        self.current_display_view = 'playlist_selection'
        self._active_combined_refresh = None
        if selected_keys is None:
            selected_keys = set(self._selected_playlist_keys_from_active_display())

        self._clear_display_frame()

        header_frame = ttk.Frame(self.display_frame)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)

        title = ttk.Label(header_frame, text="Selected Playlists", font=("Helvetica", 15, "bold"))
        title.grid(row=0, column=0, sticky=tk.W)

        settings_button = ttk.Button(header_frame, text="Settings", command=self.show_settings_display)
        settings_button.grid(row=0, column=1, sticky=tk.E)

        selector_frame = ttk.LabelFrame(self.display_frame, text="Playlists", padding=(8, 6))
        selector_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.display_playlist_vars = self._build_playlist_checkbox_selector(
            selector_frame,
            selected_keys=selected_keys
        )

        action_frame = ttk.Frame(self.display_frame)
        action_frame.grid(row=2, column=0, sticky=tk.E, pady=(8, 0))

        select_all_button = ttk.Button(
            action_frame,
            text="Select All",
            command=lambda: self._set_playlist_selection(self.display_playlist_vars, True)
        )
        select_all_button.grid(row=0, column=0, padx=5)

        clear_button = ttk.Button(
            action_frame,
            text="Clear",
            command=lambda: self._set_playlist_selection(self.display_playlist_vars, False)
        )
        clear_button.grid(row=0, column=1, padx=5)

        self.display_frame.columnconfigure(0, weight=1)
        self.display_frame.rowconfigure(1, weight=1)

    def show_combined_songs_display(self, playlist_keys, live=False):
        playlist_count = len(playlist_keys)

        def build_combined_display(parent):
            self.current_display_view = 'combined'
            self._active_combined_refresh = None
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(1, weight=1)

            header_frame = ttk.Frame(parent)
            header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            header_frame.columnconfigure(0, weight=1)

            title_text = "Combined Songs" if live else f"Combined Songs ({playlist_count} playlists)"
            title = ttk.Label(header_frame, text=title_text, font=("Helvetica", 15, "bold"))
            title.grid(row=0, column=0, sticky=tk.W)

            results_frame = ttk.Frame(parent)
            results_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            results_playlist_keys = self._selected_sidebar_playlist_keys if live else playlist_keys
            self._build_combined_songs_results(results_frame, results_playlist_keys, live=live)

        self._show_display("Combined Songs", build_combined_display, geometry="900x560")

    def _set_playlist_selection(self, playlist_vars, selected):
        for _, selected_var in playlist_vars:
            selected_var.set(selected)
        self._refresh_live_combined_if_active()

    def _selected_playlist_keys(self, playlist_vars):
        return [playlist_key for playlist_key, selected_var in playlist_vars if selected_var.get()]

    def _build_playlist_checkbox_selector(self, parent, on_change=None, selected_keys=None):
        list_frame = ttk.Frame(parent)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        canvas = tk.Canvas(list_frame, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        checkbox_frame = ttk.Frame(canvas)

        checkbox_window = canvas.create_window((0, 0), window=checkbox_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def update_checkbox_width(event):
            canvas.itemconfigure(checkbox_window, width=event.width)

        def on_mousewheel(event):
            if getattr(event, 'num', None) == 4:
                scroll_units = -3
            elif getattr(event, 'num', None) == 5:
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

        playlist_vars = []
        for row_index, playlist_key in enumerate(self.saved_playlists.keys()):
            pl_data = self.saved_playlists[playlist_key]
            source = pl_data.get('source', 'youtube')
            playlist_name = pl_data.get('name', f'Playlist {playlist_key}')
            song_count = len(pl_data.get('tracks') or pl_data.get('videos', set()))
            selected_var = tk.BooleanVar(value=selected_keys is None or playlist_key in selected_keys)
            playlist_vars.append((playlist_key, selected_var))

            row_frame = ttk.Frame(checkbox_frame, padding=(0, 1))
            row_frame.grid(row=row_index, column=0, sticky=(tk.W, tk.E))
            checkbox_frame.columnconfigure(0, weight=1)
            row_frame.columnconfigure(1, weight=1)

            badge = self._create_source_badge(row_frame, source)
            badge.grid(row=0, column=0, padx=(0, 5), sticky=tk.W)

            checkbutton = ttk.Checkbutton(
                row_frame,
                text=f"{playlist_name} ({song_count} songs)",
                variable=selected_var,
                command=on_change
            )
            checkbutton.grid(row=0, column=1, sticky=tk.W)
            for widget in (row_frame, badge, checkbutton):
                bind_mousewheel(widget)

        return playlist_vars

    def _build_combined_songs_results(self, parent, playlist_keys, live=False):
        parent.columnconfigure(5, weight=1)
        parent.rowconfigure(1, weight=1)

        sort_label = ttk.Label(parent, text="Sort by:")
        sort_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 6), pady=(0, 10))

        sort_var = tk.StringVar(value='Title (A-Z)')
        sort_combo = ttk.Combobox(
            parent,
            textvariable=sort_var,
            values=list(self.COMBINED_SORT_OPTIONS.keys()),
            state='readonly',
            width=24
        )
        sort_combo.grid(row=0, column=1, sticky=tk.W, pady=(0, 10))

        merge_duplicates_var = tk.BooleanVar(value=True)
        merge_duplicates_check = ttk.Checkbutton(
            parent,
            text="Merge duplicate songs",
            variable=merge_duplicates_var
        )
        merge_duplicates_check.grid(row=0, column=2, sticky=tk.W, padx=12, pady=(0, 10))

        display_find_var = tk.StringVar()
        find_label, find_entry = self._create_display_find_controls(parent, display_find_var)
        find_label.grid(row=0, column=3, sticky=tk.E, padx=(12, 4), pady=(0, 10))
        find_entry.grid(row=0, column=4, sticky=tk.E, pady=(0, 10))

        count_var = tk.StringVar(value="")
        count_label = ttk.Label(parent, textvariable=count_var)
        count_label.grid(row=0, column=5, sticky=tk.E, pady=(0, 10))

        table_frame = ttk.Frame(parent)
        table_frame.grid(row=1, column=0, columnspan=6, sticky=(tk.W, tk.E, tk.N, tk.S))

        y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        songs_tree = ttk.Treeview(
            table_frame,
            columns=('title', 'artist', 'playlists', 'count'),
            show='tree headings',
            style="SourceLogo.Treeview",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )
        songs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        y_scrollbar.config(command=songs_tree.yview)
        x_scrollbar.config(command=songs_tree.xview)

        songs_tree.heading('#0', text='')
        songs_tree.heading('title', text='Title')
        songs_tree.heading('artist', text='Artist')
        songs_tree.heading('playlists', text='Playlists')
        songs_tree.heading('count', text='Count')

        songs_tree.column('#0', width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
        songs_tree.column('title', width=260, minwidth=160)
        songs_tree.column('artist', width=190, minwidth=120)
        songs_tree.column('playlists', width=360, minwidth=180)
        songs_tree.column('count', width=70, minwidth=60, stretch=False, anchor=tk.CENTER)

        def refresh_results(*_):
            selected_playlist_keys = playlist_keys() if callable(playlist_keys) else playlist_keys
            entries = self._collect_combined_tracks(
                selected_playlist_keys,
                merge_duplicates=merge_duplicates_var.get()
            )
            entries = self._sort_combined_tracks(entries, sort_var.get())
            filtered_entries = [
                entry
                for entry in entries
                if self._matches_find_query(
                    (
                        entry['title'],
                        entry['artist'],
                        ', '.join(sorted(entry['playlists'])),
                        ', '.join(sorted(self._source_name(source) for source in entry['sources']))
                    ),
                    display_find_var.get()
                )
            ]

            for item_id in songs_tree.get_children():
                songs_tree.delete(item_id)

            if not filtered_entries:
                message = 'No songs found for the selected playlists.'
                if entries:
                    message = 'No songs match the current find text.'
                songs_tree.insert(
                    '',
                    tk.END,
                    values=(message, '', '', '')
                )
            else:
                for entry in filtered_entries:
                    playlists = ', '.join(sorted(entry['playlists']))
                    count = entry['appearance_count'] if entry['appearance_count'] > 1 else ''
                    songs_tree.insert(
                        '',
                        tk.END,
                        image=self._source_logo_for_sources(entry['sources']),
                        values=(entry['title'], entry['artist'], playlists, count)
                    )

            if display_find_var.get().strip() and len(filtered_entries) != len(entries):
                count_var.set(f"{len(filtered_entries)} of {len(entries)} songs")
            else:
                count_var.set(f"{len(entries)} songs")

        sort_combo.bind("<<ComboboxSelected>>", refresh_results)
        merge_duplicates_check.config(command=refresh_results)
        display_find_var.trace_add("write", refresh_results)
        if live:
            self._active_combined_refresh = refresh_results

        refresh_results()

    def _find_duplicate_entries(self, playlist_keys):
        combined_entries = self._collect_combined_tracks(playlist_keys, merge_duplicates=True)
        return [
            entry
            for entry in combined_entries
            if entry['appearance_count'] > 1
        ]

    def show_duplicate_songs_display(self, duplicate_entries, selected_count):
        duplicate_entries = sorted(
            duplicate_entries,
            key=lambda entry: (-entry['appearance_count'], entry['title'].lower(), entry['artist'].lower())
        )

        def build_duplicate_display(parent):
            self.current_display_view = 'duplicates'
            self._active_combined_refresh = None
            parent.columnconfigure(0, weight=1)
            parent.rowconfigure(1, weight=1)

            header_frame = ttk.Frame(parent)
            header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
            header_frame.columnconfigure(0, weight=1)

            title_var = tk.StringVar()
            title = ttk.Label(header_frame, textvariable=title_var, font=("Helvetica", 15, "bold"))
            title.grid(row=0, column=0, sticky=tk.W)

            display_find_var = tk.StringVar()
            find_label, find_entry = self._create_display_find_controls(header_frame, display_find_var)
            find_label.grid(row=0, column=1, sticky=tk.E, padx=(12, 4))
            find_entry.grid(row=0, column=2, sticky=tk.E)

            table_frame = ttk.Frame(parent)
            table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            y_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
            y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            x_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
            x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

            duplicates_tree = ttk.Treeview(
                table_frame,
                columns=('title', 'artist'),
                show='tree headings',
                style="SourceLogo.Treeview",
                yscrollcommand=y_scrollbar.set,
                xscrollcommand=x_scrollbar.set
            )
            duplicates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            y_scrollbar.config(command=duplicates_tree.yview)
            x_scrollbar.config(command=duplicates_tree.xview)

            duplicates_tree.heading('#0', text='')
            duplicates_tree.heading('title', text='Title')
            duplicates_tree.heading('artist', text='Artist')

            duplicates_tree.column('#0', width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
            duplicates_tree.column('title', width=360, minwidth=180)
            duplicates_tree.column('artist', width=260, minwidth=140)

            def refresh_duplicate_rows(*_):
                for item_id in duplicates_tree.get_children():
                    duplicates_tree.delete(item_id)

                visible_entries = [
                    entry
                    for entry in duplicate_entries
                    if self._matches_find_query(
                        (
                            entry['title'],
                            entry['artist'],
                            ', '.join(sorted(entry['playlists'])),
                            ', '.join(sorted(self._source_name(source) for source in entry['sources']))
                        ),
                        display_find_var.get()
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
                    duplicates_tree.insert(
                        '',
                        tk.END,
                        values=(message, '')
                    )
                    return

                for entry in visible_entries:
                    duplicates_tree.insert(
                        '',
                        tk.END,
                        image=self._source_logo_for_sources(entry['sources']),
                        values=(entry['title'], entry['artist'])
                    )

            display_find_var.trace_add("write", refresh_duplicate_rows)
            refresh_duplicate_rows()

        self._show_display("Selected Playlist Duplicates", build_duplicate_display, geometry="900x560")
    
    def find_duplicate_songs(self):
        """Find and display songs that appear multiple times in selected playlists"""
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first")
            return

        selected_playlist_keys = self._selected_sidebar_playlist_keys()
        if not selected_playlist_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist.")
            return

        try:
            duplicates = self._find_duplicate_entries(selected_playlist_keys)
            self.show_duplicate_songs_display(duplicates, len(selected_playlist_keys))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to find duplicates: {e}")
    
    def update_selected_playlists(self):
        """Update selected saved playlists with latest data from their source"""
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "You have no saved playlists to update.")
            return

        selected_playlist_keys = self._selected_sidebar_playlist_keys()
        if not selected_playlist_keys:
            messagebox.showwarning("No Selection", "Please choose at least one playlist to update.")
            return

        try:
            updated_count = 0
            failed_playlists = []
            cancelled = {'value': False}
            
            # Create a progress window
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Updating Playlists")
            progress_window.geometry("400x150")
            progress_window.resizable(False, False)
            
            main_frame = ttk.Frame(progress_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Title
            title = ttk.Label(main_frame, text="Updating Selected Playlists", font=("Helvetica", 12, "bold"))
            title.grid(row=0, column=0, columnspan=2, pady=10)
            
            # Status label
            status_label = ttk.Label(main_frame, text="")
            status_label.grid(row=1, column=0, columnspan=2, pady=10)
            
            # Progress bar
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(main_frame, variable=progress_var, maximum=100, length=300)
            progress_bar.grid(row=2, column=0, columnspan=2, pady=10)

            def cancel_update():
                cancelled['value'] = True
                status_label.config(text="Cancelling after current playlist...")

            # Cancel button
            cancel_button = ttk.Button(main_frame, text="Cancel", command=cancel_update)
            cancel_button.grid(row=3, column=0, columnspan=2, pady=10)
            progress_window.protocol("WM_DELETE_WINDOW", cancel_update)
            
            progress_window.update()
            
            total_playlists = len(selected_playlist_keys)
            
            for idx, playlist_key in enumerate(selected_playlist_keys):
                if cancelled['value']:
                    break

                try:
                    pl_data = self.saved_playlists.get(playlist_key)
                    if not pl_data:
                        continue

                    pl_name = pl_data.get('name', f'Playlist {playlist_key}')
                    status_label.config(text=f"Updating: {pl_name}...")
                    progress_var.set((idx / total_playlists) * 100)
                    progress_window.update()

                    source, playlist_id = self._normalize_playlist_identity(playlist_key, pl_data)
                    if source == 'youtube':
                        self.saved_playlists[playlist_key] = self._fetch_youtube_playlist_entry(playlist_id, pl_name)
                    elif source == 'spotify':
                        self.saved_playlists[playlist_key] = self._fetch_spotify_playlist_entry(playlist_id, pl_name)
                    else:
                        raise RuntimeError(f"Unsupported playlist source: {source}")

                    updated_count += 1
                    
                except Exception as e:
                    print(f"Error updating playlist {playlist_key}: {e}")
                    failed_playlists.append(pl_name)
            
            # Save updated playlists
            self.save_playlists()
            self.refresh_playlist_selectors(selected_keys=set(selected_playlist_keys))
            self._refresh_live_combined_if_active()
            
            # Update progress bar to 100%
            progress_var.set(100)
            progress_window.update()
            
            # Close progress window
            progress_window.destroy()
            
            # Show results
            if cancelled['value']:
                message = f"Updated {updated_count} of {total_playlists} selected playlists before cancelling."
                if failed_playlists:
                    message += "\n\nFailed to update:\n" + "\n".join(failed_playlists)
                messagebox.showinfo("Update Cancelled", message)
            elif failed_playlists:
                message = f"Updated {updated_count} of {total_playlists} selected playlists.\n\nFailed to update:\n" + "\n".join(failed_playlists)
                messagebox.showwarning("Update Complete", message)
            else:
                messagebox.showinfo("Success", f"Successfully updated {updated_count} selected playlists!")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update playlists: {e}")


class PlaylistURLWindow:
    def __init__(self, parent, ytmusic, saved_playlists, parent_ui, source='youtube'):
        self.source = source
        self.window = tk.Toplevel(parent)
        self.window.title("Add Spotify Playlist URL" if self.source == 'spotify' else "Add YouTube Playlist URL")
        self.window.geometry("500x220")
        self.ytmusic = ytmusic
        self.saved_playlists = saved_playlists
        self.parent_ui = parent_ui
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_text = "Paste Spotify Playlist URL" if self.source == 'spotify' else "Paste YouTube Playlist URL"
        title = ttk.Label(main_frame, text=title_text, font=("Helvetica", 12, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # URL label
        url_label = ttk.Label(main_frame, text="Playlist URL:")
        url_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # URL entry
        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        self.url_entry.bind("<Return>", lambda e: self.on_submit())
        
        # Submit button
        submit_text = "Add Spotify Playlist" if self.source == 'spotify' else "Add YouTube Playlist"
        submit_button = ttk.Button(main_frame, text=submit_text, command=self.on_submit)
        submit_button.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Configure grid weights
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
    
    def on_submit(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input", "Please enter a playlist URL")
            return

        if self.source == 'youtube' and not self.ytmusic:
            messagebox.showerror("Error", "YTMusic not initialized")
            return

        if self.source == 'spotify' and not self.parent_ui.spotapi_available:
            messagebox.showerror(
                "Error",
                "Spotify support is not available. Install spotapi (pip install spotapi) to enable adding public Spotify playlists."
            )
            return

        try:
            playlist_id = self._extract_playlist_id(url)
            if not playlist_id:
                messagebox.showerror("Error", "Invalid playlist URL format")
                return

            if self.source == 'youtube':
                playlist_entry = self.parent_ui._fetch_youtube_playlist_entry(playlist_id)
            else:
                playlist_entry = self.parent_ui._fetch_spotify_playlist_entry(playlist_id)

            playlist_name = playlist_entry['name']
            saved_count = len(playlist_entry['videos'])
            store_key = self.parent_ui._playlist_storage_key(self.source, playlist_id)
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
    
    def _extract_playlist_id(self, url):
        if self.source == 'spotify':
            return self._extract_spotify_playlist_id(url)
        return self._extract_youtube_playlist_id(url)

    def _extract_youtube_playlist_id(self, url):
        """Extract playlist ID from YouTube Music URL"""
        # Handle different URL formats
        patterns = [
            r'list=([a-zA-Z0-9_-]+)',  # ?list=ID
            r'playlist/([a-zA-Z0-9_-]+)',  # /playlist/ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # If URL is just the ID
        if len(url) > 20 and '/' not in url:
            return url

        return None

    def _extract_spotify_playlist_id(self, url):
        """Extract playlist ID from Spotify URL"""
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
