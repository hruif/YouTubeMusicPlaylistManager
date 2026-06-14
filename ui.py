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
    SOURCE_ICONS = {
        'youtube': '▶',
        'spotify': '🎵'
    }

    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Music Public Playlist Manager")
        self.root.geometry("800x520")
        self.root.minsize(800, 520)
        
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
        
        # Main frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(main_frame, text="YouTube + Spotify Playlist Manager", font=("Helvetica", 16, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=20)
        
        # Search bar label
        search_label = ttk.Label(main_frame, text="Search songs in your playlists:")
        search_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # Search entry
        self.search_entry = ttk.Entry(main_frame, width=50)
        self.search_entry.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Search button
        search_button = ttk.Button(button_frame, text="Search", command=self.on_search)
        search_button.grid(row=0, column=0, padx=5, pady=2)
        
        # Add YouTube Playlist button
        add_playlist_button = ttk.Button(button_frame, text="Add YouTube Playlist URL", command=self.open_playlist_window)
        add_playlist_button.grid(row=0, column=1, padx=5, pady=2)

        # Add Spotify Playlist button
        add_spotify_button = ttk.Button(button_frame, text="Add Spotify Playlist URL", command=self.open_spotify_playlist_window)
        add_spotify_button.grid(row=0, column=2, padx=5, pady=2)
        
        # View Playlists button
        view_playlists_button = ttk.Button(button_frame, text="View Saved Playlists", command=self.view_saved_playlists)
        view_playlists_button.grid(row=0, column=3, padx=5, pady=2)
        
        # Find Duplicates button
        find_duplicates_button = ttk.Button(button_frame, text="Find Duplicate Songs", command=self.find_duplicate_songs)
        find_duplicates_button.grid(row=1, column=0, padx=5, pady=2)
        
        # Update All Playlists button
        update_all_button = ttk.Button(button_frame, text="Update All Playlists", command=self.update_all_playlists)
        update_all_button.grid(row=1, column=1, padx=5, pady=2)
        
        # Results text area
        results_label = ttk.Label(main_frame, text="Songs in Your Playlists:")
        results_label.grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        
        # Results text widget
        self.results_text = tk.Text(main_frame, height=10, width=80, state=tk.DISABLED)
        self.results_text.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Configure grid weights
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
    
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
            if source in self.SOURCE_ICONS and playlist_id:
                return source, playlist_id
        return 'youtube', stored_key

    def _normalize_playlist_identity(self, stored_key, pl_data):
        stored_source, stored_playlist_id = self._split_storage_key(stored_key)

        source = pl_data.get('source') or stored_source
        if source not in self.SOURCE_ICONS:
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

    def _find_matching_tracks(self, query):
        query_terms = [term for term in self._normalize_search_text(query).split() if term]
        if not query_terms:
            return {}

        matches = {}
        for pl_id, pl_data in self.saved_playlists.items():
            playlist_name = pl_data.get('name', f'Playlist {pl_id}')
            source = pl_data.get('source', 'youtube')
            source_label = f"{self.SOURCE_ICONS.get(source, '?')} {playlist_name}"
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

    def on_search(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Input", "Please enter a song name")
            return
        
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first")
            return

        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)

        filtered_results = self._find_matching_tracks(query)
        if not filtered_results:
            self.results_text.insert(tk.END, f"No songs matching '{query}' were found in your saved playlists.\n\nTry a different query or add more playlists.")
            self.results_text.config(state=tk.DISABLED)
            return

        sorted_results = sorted(
            filtered_results.values(),
            key=lambda entry: entry['track'].get('title', '').lower()
        )

        for i, entry in enumerate(sorted_results, 1):
            track = entry['track']
            in_playlists = sorted(entry['playlists'])
            title = track.get('title', 'Unknown')
            artist = track.get('artist', 'Unknown')

            result_str = f"{i}. {title} by {artist}\n   Found in: {', '.join(in_playlists)}\n\n"
            self.results_text.insert(tk.END, result_str)

        self.results_text.config(state=tk.DISABLED)
    
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
        
        # Create a new window
        view_window = tk.Toplevel(self.root)
        view_window.title("Saved Playlists")
        view_window.geometry("600x400")
        
        # Main frame
        main_frame = ttk.Frame(view_window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(main_frame, text=f"Saved Playlists ({len(self.saved_playlists)})", font=("Helvetica", 14, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # Create a frame for the playlist list
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create text widget for playlists
        playlists_text = tk.Text(list_frame, height=15, width=70, yscrollcommand=scrollbar.set)
        playlists_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=playlists_text.yview)
        
        # Populate the text widget
        for i, (pl_id, pl_data) in enumerate(self.saved_playlists.items(), 1):
            name = pl_data.get('name', 'Unnamed')
            song_count = len(pl_data.get('videos', set()))
            source = pl_data.get('source', 'youtube')
            icon = self.SOURCE_ICONS.get(source, '?')
            playlists_text.insert(tk.END, f"{i}. {icon} {name}\n")
            playlists_text.insert(tk.END, f"   ID: {pl_id}\n")
            playlists_text.insert(tk.END, f"   Source: {source.title()}\n")
            playlists_text.insert(tk.END, f"   Songs: {song_count}\n\n")
        
        playlists_text.config(state=tk.DISABLED)
        
        # Close button
        close_button = ttk.Button(main_frame, text="Close", command=view_window.destroy)
        close_button.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Configure grid weights
        view_window.columnconfigure(0, weight=1)
        view_window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
    
    def find_duplicate_songs(self):
        """Find and display songs that appear in multiple playlists"""
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "Please add at least one playlist first")
            return
        
        if len(self.saved_playlists) < 2:
            messagebox.showinfo("Not Enough Playlists", "You need at least 2 playlists to find duplicates.\n\nAdd more playlists to use this feature.")
            return
        
        try:
            # Create a mapping of track ID to playlists that contain it, and track metadata
            track_to_playlists = {}
            track_to_track = {}  # Store track metadata
            
            for pl_id, pl_data in self.saved_playlists.items():
                source = pl_data.get('source', 'youtube')
                playlist_name = pl_data.get('name', f'Playlist {pl_id}')
                playlist_label = f"{self.SOURCE_ICONS.get(source, '?')} {playlist_name}"
                tracks = pl_data.get('tracks', [])
                
                for track in tracks:
                    title = track.get('title', '')
                    artist = track.get('artist', '')
                    track_key = self._normalize_song_key(title, artist)
                    if track_key:
                        if track_key not in track_to_playlists:
                            track_to_playlists[track_key] = set()
                            track_to_track[track_key] = track
                        track_to_playlists[track_key].add(playlist_label)
            
            # Filter to only duplicates (songs in more than one playlist)
            duplicates = {
                vid: playlists
                for vid, playlists in track_to_playlists.items()
                if len(playlists) > 1
            }
            
            if not duplicates:
                messagebox.showinfo("No Duplicates Found", "No songs were found in multiple playlists.\n\nAll songs in your playlists are unique!")
                return
            
            # Create results window
            results_window = tk.Toplevel(self.root)
            results_window.title("Duplicate Songs Found")
            results_window.geometry("700x500")
            
            # Main frame
            main_frame = ttk.Frame(results_window, padding="20")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            
            # Title
            title = ttk.Label(main_frame, text=f"Duplicate Songs ({len(duplicates)} found)", font=("Helvetica", 14, "bold"))
            title.grid(row=0, column=0, columnspan=2, pady=10)
            
            # Create a frame for the results
            results_frame = ttk.Frame(main_frame)
            results_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
            
            # Add scrollbar
            scrollbar = ttk.Scrollbar(results_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            # Create text widget for results
            results_text = tk.Text(results_frame, height=20, width=80, yscrollcommand=scrollbar.set)
            results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=results_text.yview)
            
            # Clear and populate with actual results
            results_text.delete(1.0, tk.END)
            
            # Sort duplicates by number of playlists (most duplicated first)
            sorted_duplicates = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)
            
            for i, (video_id, playlists) in enumerate(sorted_duplicates, 1):
                # Get song details from stored metadata
                track = track_to_track.get(video_id, {})
                title = track.get('title', f'Song ID: {video_id}')
                artist = track.get('artist', 'Unknown Artist')
                
                # Format result
                results_text.insert(tk.END, f"{i}. {title}\n")
                results_text.insert(tk.END, f"   by {artist}\n")
                results_text.insert(tk.END, f"   Found in {len(playlists)} playlists: {', '.join(sorted(playlists))}\n\n")
            
            results_text.config(state=tk.DISABLED)
            
            # Close button
            close_button = ttk.Button(main_frame, text="Close", command=results_window.destroy)
            close_button.grid(row=2, column=0, columnspan=2, pady=10)
            
            # Configure grid weights
            results_window.columnconfigure(0, weight=1)
            results_window.rowconfigure(0, weight=1)
            main_frame.columnconfigure(0, weight=1)
            main_frame.rowconfigure(1, weight=1)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to find duplicates: {e}")
    
    def update_all_playlists(self):
        """Update all saved playlists with latest data from their source"""
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "You have no saved playlists to update.")
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
            title = ttk.Label(main_frame, text="Updating All Playlists", font=("Helvetica", 12, "bold"))
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
            
            total_playlists = len(self.saved_playlists)
            
            for idx, (playlist_key, pl_data) in enumerate(self.saved_playlists.items()):
                if cancelled['value']:
                    break

                try:
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
            
            # Update progress bar to 100%
            progress_var.set(100)
            progress_window.update()
            
            # Close progress window
            progress_window.destroy()
            
            # Show results
            if cancelled['value']:
                message = f"Updated {updated_count} of {total_playlists} playlists before cancelling."
                if failed_playlists:
                    message += "\n\nFailed to update:\n" + "\n".join(failed_playlists)
                messagebox.showinfo("Update Cancelled", message)
            elif failed_playlists:
                message = f"Updated {updated_count} of {total_playlists} playlists.\n\nFailed to update:\n" + "\n".join(failed_playlists)
                messagebox.showwarning("Update Complete", message)
            else:
                messagebox.showinfo("Success", f"Successfully updated all {updated_count} playlists!")
        
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
