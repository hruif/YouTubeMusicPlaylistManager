#!/usr/bin/env python3
"""
Test playlist title extraction with real data
"""

def test_playlist_title_extraction():
    print("Testing playlist title extraction...")

    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()

        # Test with a few different playlist approaches
        test_cases = [
            # Try to get a playlist from search results first
            ("search_first", None),
        ]

        # First, let's search for playlists to get a real playlist ID
        print("Searching for playlists...")
        search_results = ytm.search("top hits", filter="playlists", limit=5)

        if search_results:
            print(f"Found {len(search_results)} playlists")
            for i, pl in enumerate(search_results[:2]):  # Test first 2
                try:
                    pl_id = pl.get('playlistId') or pl.get('browseId')
                    if pl_id:
                        print(f"\nTesting playlist {i+1}: {pl_id}")
                        playlist = ytm.get_playlist(pl_id, limit=1)  # Small limit for testing

                        # Test our extraction logic
                        playlist_name = extract_playlist_title(playlist)
                        print(f"Extracted title: '{playlist_name}'")

                        # Show the raw structure for debugging
                        print(f"Raw title field: {playlist.get('title')}")
                        if 'header' in playlist:
                            print(f"Header title: {playlist['header'].get('title')}")

                except Exception as e:
                    print(f"Error testing playlist {i+1}: {e}")
        else:
            print("No playlists found in search")

    except Exception as e:
        print(f"Error: {e}")

def extract_playlist_title(playlist):
    """Extract playlist title with multiple fallbacks"""
    # Try direct title first
    playlist_name = playlist.get('title')
    if playlist_name:
        return playlist_name

    # Try header location (old method)
    playlist_name = playlist.get('header', {}).get('title', 'Unnamed Playlist')
    if playlist_name and playlist_name != 'Unnamed Playlist':
        return playlist_name

    # Try nested renderer structures
    if 'header' in playlist and isinstance(playlist['header'], dict):
        header = playlist['header']
        if 'musicDetailHeaderRenderer' in header:
            renderer = header['musicDetailHeaderRenderer']
            if 'title' in renderer and isinstance(renderer['title'], dict):
                runs = renderer['title'].get('runs', [])
                if runs and isinstance(runs[0], dict):
                    return runs[0].get('text', 'Unnamed Playlist')

    return 'Unnamed Playlist'

if __name__ == "__main__":
    test_playlist_title_extraction()