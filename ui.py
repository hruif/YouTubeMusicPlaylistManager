import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from ytmusicapi import YTMusic

class PlaylistManagerUI:
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
        
        # Store saved playlists
        self.saved_playlists = {}  # {playlist_id: {name, tracks}}
        self.playlists_file = "saved_playlists.json"
        
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
        title = ttk.Label(main_frame, text="YouTube Music Public Playlist Manager", font=("Helvetica", 16, "bold"))
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
        
        # Add Playlist button
        add_playlist_button = ttk.Button(button_frame, text="Add Public Playlist URL", command=self.open_playlist_window)
        add_playlist_button.grid(row=0, column=1, padx=5, pady=2)
        
        # View Playlists button
        view_playlists_button = ttk.Button(button_frame, text="View Saved Playlists", command=self.view_saved_playlists)
        view_playlists_button.grid(row=0, column=2, padx=5, pady=2)
        
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
            if os.path.exists(self.playlists_file):
                with open(self.playlists_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Validate the data structure and convert lists back to sets
                    if isinstance(data, dict):
                        self.saved_playlists = {}
                        for pl_id, pl_data in data.items():
                            if isinstance(pl_data, dict) and 'videos' in pl_data:
                                # Convert video list back to set
                                videos = set(pl_data['videos']) if isinstance(pl_data['videos'], list) else pl_data['videos']
                                
                                # Handle tracks data (new format) or create from videos (old format)
                                tracks = pl_data.get('tracks', [])
                                if not tracks and videos:
                                    # For old format, try to get track metadata from YouTube Music
                                    tracks = []
                                    try:
                                        # Get playlist data to extract track metadata
                                        playlist_data = self.ytmusic.get_playlist(pl_id, limit=500)
                                        for track in playlist_data.get('tracks', []):
                                            if track.get('videoId') in videos:
                                                title = track.get('title', 'Unknown Title')
                                                artists = track.get('artists', [])
                                                artist = artists[0].get('name', 'Unknown Artist') if artists else 'Unknown Artist'
                                                tracks.append({
                                                    'videoId': track['videoId'],
                                                    'title': title,
                                                    'artist': artist
                                                })
                                    except Exception as e:
                                        print(f"Could not fetch metadata for playlist {pl_id}: {e}")
                                        # Fallback: create dummy tracks
                                        tracks = [{'videoId': vid, 'title': f'Song ID: {vid}', 'artist': 'Unknown'} for vid in videos]
                                
                                self.saved_playlists[pl_id] = {
                                    'name': pl_data.get('name', 'Unnamed Playlist'),
                                    'videos': videos,
                                    'tracks': tracks
                                }
                        print(f"Loaded {len(self.saved_playlists)} playlists from {self.playlists_file}")
                        
                        # Save updated format if we migrated old playlists
                        has_old_format = any('tracks' not in pl_data for pl_data in data.values() if isinstance(pl_data, dict))
                        if has_old_format:
                            print("Migrating old playlist format to include track metadata...")
                            self.save_playlists()
                            print("Migration complete.")
                    else:
                        print("Invalid playlist data format, starting fresh")
                        self.saved_playlists = {}
            else:
                print("No saved playlists file found, starting fresh")
                self.saved_playlists = {}
        except json.JSONDecodeError as e:
            print(f"Corrupted playlist file: {e}, starting fresh")
            self.saved_playlists = {}
            # Backup the corrupted file
            if os.path.exists(self.playlists_file):
                backup_file = f"{self.playlists_file}.backup"
                os.rename(self.playlists_file, backup_file)
                print(f"Backed up corrupted file to {backup_file}")
        except Exception as e:
            print(f"Error loading playlists: {e}")
            self.saved_playlists = {}
    
    def save_playlists(self):
        """Save playlists to file"""
        try:
            # Convert sets to lists for JSON serialization
            json_data = {}
            for pl_id, pl_data in self.saved_playlists.items():
                json_data[pl_id] = {
                    'name': pl_data['name'],
                    'videos': list(pl_data['videos']),  # convert set to list
                    'tracks': pl_data.get('tracks', [])  # include tracks metadata
                }
            
            # Create a backup of the existing file if it exists
            if os.path.exists(self.playlists_file):
                backup_file = f"{self.playlists_file}.backup"
                os.replace(self.playlists_file, backup_file)
            
            # Save the new data
            with open(self.playlists_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.saved_playlists)} playlists to {self.playlists_file}")
        except Exception as e:
            print(f"Error saving playlists: {e}")
            messagebox.showerror("Error", f"Failed to save playlists: {e}")
            # Try to restore backup
            backup_file = f"{self.playlists_file}.backup"
            if os.path.exists(backup_file):
                os.replace(backup_file, self.playlists_file)
                print("Restored backup file")
    
    def _extract_playlist_name(self, playlist, fallback_name='Unnamed Playlist'):
        playlist_name = playlist.get('title')
        if playlist_name:
            return playlist_name

        playlist_name = playlist.get('header', {}).get('title')
        if playlist_name and playlist_name != 'Unnamed Playlist':
            return playlist_name

        header = playlist.get('header')
        if isinstance(header, dict):
            renderer = header.get('musicDetailHeaderRenderer')
            if isinstance(renderer, dict):
                title_data = renderer.get('title')
                if isinstance(title_data, dict):
                    runs = title_data.get('runs', [])
                    if runs and isinstance(runs[0], dict):
                        return runs[0].get('text', fallback_name)

        return fallback_name

    def _extract_track_metadata(self, playlist):
        tracks_data = []
        video_ids = set()

        for track in playlist.get('tracks', []):
            if 'videoId' not in track:
                continue

            video_id = track['videoId']
            video_ids.add(video_id)

            title = track.get('title', 'Unknown Title')
            artists = track.get('artists', [])
            artist = artists[0].get('name', 'Unknown Artist') if artists else 'Unknown Artist'

            tracks_data.append({
                'videoId': video_id,
                'title': title,
                'artist': artist
            })

        return video_ids, tracks_data

    def _find_matching_tracks(self, query):
        query_terms = [term for term in query.lower().split() if term]
        if not query_terms:
            return {}

        matches = {}
        for pl_id, pl_data in self.saved_playlists.items():
            playlist_name = pl_data.get('name', f'Playlist {pl_id}')
            for track in pl_data.get('tracks', []):
                title = track.get('title', '')
                artist = track.get('artist', '')
                searchable_text = f"{title} {artist}".lower()

                if all(term in searchable_text for term in query_terms):
                    video_id = track.get('videoId')
                    if not video_id:
                        continue

                    if video_id not in matches:
                        matches[video_id] = {
                            'track': track,
                            'playlists': set()
                        }
                    matches[video_id]['playlists'].add(playlist_name)

        return matches

    def on_search(self):
        query = self.search_entry.get()
        if not query:
            messagebox.showwarning("Input", "Please enter a song name")
            return
        
        if not self.ytmusic:
            messagebox.showerror("Error", "YTMusic not initialized")
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
        PlaylistURLWindow(self.root, self.ytmusic, self.saved_playlists, self)
    
    def view_saved_playlists(self):
        """Show a window with saved playlists"""
        if not self.saved_playlists:
            messagebox.showinfo("Saved Playlists", "No playlists saved yet.\n\nAdd some playlists using 'Add Public Playlist URL'.")
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
            playlists_text.insert(tk.END, f"{i}. {name}\n")
            playlists_text.insert(tk.END, f"   ID: {pl_id}\n")
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
        
        if not self.ytmusic:
            messagebox.showerror("Error", "YTMusic not initialized")
            return
        
        try:
            # Create a mapping of videoId to playlists that contain it, and track metadata
            video_to_playlists = {}
            video_to_track = {}  # Store track metadata
            
            for pl_id, pl_data in self.saved_playlists.items():
                pl_name = pl_data.get('name', f'Playlist {pl_id}')
                tracks = pl_data.get('tracks', [])
                
                for track in tracks:
                    video_id = track.get('videoId')
                    if video_id:
                        if video_id not in video_to_playlists:
                            video_to_playlists[video_id] = []
                            video_to_track[video_id] = track
                        video_to_playlists[video_id].append(pl_name)
            
            # Filter to only duplicates (songs in more than one playlist)
            duplicates = {vid: playlists for vid, playlists in video_to_playlists.items() 
                         if len(playlists) > 1}
            
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
                track = video_to_track.get(video_id, {})
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
        """Update all saved playlists with latest data from YouTube Music"""
        if not self.saved_playlists:
            messagebox.showwarning("No Playlists", "You have no saved playlists to update.")
            return
        
        if not self.ytmusic:
            messagebox.showerror("Error", "YTMusic not initialized")
            return
        
        try:
            updated_count = 0
            failed_playlists = []
            
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
            
            # Cancel button
            cancel_button = ttk.Button(main_frame, text="Cancel", command=progress_window.destroy)
            cancel_button.grid(row=3, column=0, columnspan=2, pady=10)
            
            progress_window.update()
            
            total_playlists = len(self.saved_playlists)
            
            for idx, (playlist_id, pl_data) in enumerate(self.saved_playlists.items()):
                try:
                    pl_name = pl_data.get('name', f'Playlist {playlist_id}')
                    status_label.config(text=f"Updating: {pl_name}...")
                    progress_var.set((idx / total_playlists) * 100)
                    progress_window.update()
                    
                    # Fetch updated playlist
                    playlist = self.ytmusic.get_playlist(playlist_id, limit=500)
                    
                    playlist_name = self._extract_playlist_name(playlist, pl_name)
                    video_ids, tracks_data = self._extract_track_metadata(playlist)

                    self.saved_playlists[playlist_id] = {
                        'name': playlist_name,
                        'videos': video_ids,
                        'tracks': tracks_data
                    }
                    
                    updated_count += 1
                    
                except Exception as e:
                    print(f"Error updating playlist {playlist_id}: {e}")
                    failed_playlists.append(pl_name)
            
            # Save updated playlists
            self.save_playlists()
            
            # Update progress bar to 100%
            progress_var.set(100)
            progress_window.update()
            
            # Close progress window
            progress_window.destroy()
            
            # Show results
            if failed_playlists:
                message = f"Updated {updated_count} of {total_playlists} playlists.\n\nFailed to update:\n" + "\n".join(failed_playlists)
                messagebox.showwarning("Update Complete", message)
            else:
                messagebox.showinfo("Success", f"Successfully updated all {updated_count} playlists!")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update playlists: {e}")


class PlaylistURLWindow:
    def __init__(self, parent, ytmusic, saved_playlists, parent_ui):
        self.window = tk.Toplevel(parent)
        self.window.title("Add Public Playlist URL")
        self.window.geometry("500x200")
        self.ytmusic = ytmusic
        self.saved_playlists = saved_playlists
        self.parent_ui = parent_ui
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title = ttk.Label(main_frame, text="Paste Public Playlist URL", font=("Helvetica", 12, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)
        
        # URL label
        url_label = ttk.Label(main_frame, text="Playlist URL:")
        url_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # URL entry
        self.url_entry = ttk.Entry(main_frame, width=50)
        self.url_entry.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        self.url_entry.bind("<Return>", lambda e: self.on_submit())
        
        # Submit button
        submit_button = ttk.Button(main_frame, text="Add Public Playlist", command=self.on_submit)
        submit_button.grid(row=3, column=0, columnspan=2, pady=10)
        
        # Configure grid weights
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
    
    def on_submit(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showwarning("Input", "Please enter a playlist URL")
            return
        
        if not self.ytmusic:
            messagebox.showerror("Error", "YTMusic not initialized")
            return
        
        try:
            # Extract playlist ID from URL
            playlist_id = self._extract_playlist_id(url)
            if not playlist_id:
                messagebox.showerror("Error", "Invalid playlist URL format")
                return
            
            # Fetch playlist
            playlist = self.ytmusic.get_playlist(playlist_id, limit=500)
            
            playlist_name = self.parent_ui._extract_playlist_name(playlist, 'Unnamed Playlist')
            video_ids, tracks_data = self.parent_ui._extract_track_metadata(playlist)
            
            # Save playlist with track metadata
            self.saved_playlists[playlist_id] = {
                'name': playlist_name,
                'videos': video_ids,  # Keep for backward compatibility
                'tracks': tracks_data  # New: store track metadata
            }
            
            # Save to file
            self.parent_ui.save_playlists()
            
            messagebox.showinfo("Success", f"Added playlist: {playlist_name}\n({len(video_ids)} songs)")
            self.window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add playlist: {e}")
    
    def _extract_playlist_id(self, url):
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
        if len(url) > 20 and not '/' in url:
            return url
        
        return None