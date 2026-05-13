#!/usr/bin/env python3
"""
Test script to examine playlist response structure
"""

def test_playlist_structure():
    print("Testing playlist response structure...")

    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()

        # Test with a known public playlist
        # Using a popular public playlist for testing
        test_playlist_id = "PLrAXtmRdnEQy5KQZF5q9F8mGQ8Xh8Xh8X"  # This might not work, but let's see

        print("Fetching playlist...")
        try:
            playlist = ytm.get_playlist(test_playlist_id, limit=5)  # Small limit for testing
            print("Playlist fetched successfully!")

            # Print the structure
            print("\n=== PLAYLIST STRUCTURE ===")
            print(f"Keys: {list(playlist.keys())}")

            if 'header' in playlist:
                print(f"\nHeader keys: {list(playlist['header'].keys())}")
                if 'title' in playlist['header']:
                    print(f"Title found in header: {playlist['header']['title']}")
                else:
                    print("No 'title' in header")

            # Look for title in other common locations
            for key in ['title', 'name', 'playlistName']:
                if key in playlist:
                    print(f"Found '{key}': {playlist[key]}")

            # Check header substructure
            if 'header' in playlist:
                header = playlist['header']
                print(f"\nHeader content: {header}")

                # Look for title in nested structures
                if 'musicDetailHeaderRenderer' in header:
                    print("Found musicDetailHeaderRenderer")
                if 'musicResponsiveHeaderRenderer' in header:
                    print("Found musicResponsiveHeaderRenderer")

        except Exception as e:
            print(f"Failed to fetch playlist: {e}")
            print("This is expected if the playlist ID is invalid")

    except ImportError:
        print("ytmusicapi not available")

def test_with_sample_data():
    print("\n=== TESTING WITH SAMPLE STRUCTURE ===")
    # Based on ytmusicapi documentation and common structures
    sample_structures = [
        {
            'header': {
                'musicDetailHeaderRenderer': {
                    'title': {'runs': [{'text': 'My Playlist'}]}
                }
            }
        },
        {
            'title': 'Direct Title'
        },
        {
            'header': {
                'title': {'runs': [{'text': 'Nested Title'}]}
            }
        }
    ]

    for i, sample in enumerate(sample_structures, 1):
        print(f"\nSample {i}:")
        print(f"Structure: {sample}")

        # Test current extraction method
        current_method = sample.get('header', {}).get('title', 'Unnamed Playlist')
        print(f"Current method result: {current_method}")

        # Test improved extraction
        improved_result = extract_playlist_title(sample)
        print(f"Improved method result: {improved_result}")

def extract_playlist_title(playlist_data):
    """Improved playlist title extraction"""
    # Try multiple possible locations for the title

    # 1. Direct title
    if 'title' in playlist_data:
        title = playlist_data['title']
        if isinstance(title, str):
            return title
        elif isinstance(title, dict) and 'runs' in title:
            return title['runs'][0]['text'] if title['runs'] else 'Unnamed Playlist'

    # 2. Header -> title
    if 'header' in playlist_data:
        header = playlist_data['header']

        # Direct title in header
        if 'title' in header:
            title = header['title']
            if isinstance(title, str):
                return title
            elif isinstance(title, dict) and 'runs' in title:
                return title['runs'][0]['text'] if title['runs'] else 'Unnamed Playlist'

        # musicDetailHeaderRenderer
        if 'musicDetailHeaderRenderer' in header:
            renderer = header['musicDetailHeaderRenderer']
            if 'title' in renderer:
                title = renderer['title']
                if isinstance(title, dict) and 'runs' in title:
                    return title['runs'][0]['text'] if title['runs'] else 'Unnamed Playlist'

        # musicResponsiveHeaderRenderer
        if 'musicResponsiveHeaderRenderer' in header:
            renderer = header['musicResponsiveHeaderRenderer']
            if 'title' in renderer:
                title = renderer['title']
                if isinstance(title, dict) and 'runs' in title:
                    return title['runs'][0]['text'] if title['runs'] else 'Unnamed Playlist'

    return 'Unnamed Playlist'

if __name__ == "__main__":
    test_playlist_structure()
    test_with_sample_data()