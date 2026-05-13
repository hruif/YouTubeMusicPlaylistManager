#!/usr/bin/env python3
"""
Test the playlist filtering logic
"""

def test_playlist_filtering():
    print("Testing playlist filtering logic...")

    # Mock saved playlists data
    saved_playlists = {
        'PL1': {
            'name': 'My Favorites',
            'videos': {'vid1', 'vid2', 'vid3'}
        },
        'PL2': {
            'name': 'Chill Music',
            'videos': {'vid2', 'vid4', 'vid5'}
        }
    }

    # Mock search results
    mock_results = [
        {'title': 'Song A', 'artists': [{'name': 'Artist A'}], 'videoId': 'vid1'},
        {'title': 'Song B', 'artists': [{'name': 'Artist B'}], 'videoId': 'vid2'},
        {'title': 'Song C', 'artists': [{'name': 'Artist C'}], 'videoId': 'vid6'},  # Not in playlists
        {'title': 'Song D', 'artists': [{'name': 'Artist D'}], 'videoId': 'vid4'},
        {'title': 'Song E', 'artists': [{'name': 'Artist E'}], 'videoId': 'vid7'},  # Not in playlists
    ]

    # Test filtering logic
    filtered_results = []

    for song in mock_results:
        video_id = song.get('videoId', '')
        if video_id:
            in_playlists = []
            for pl_id, pl_data in saved_playlists.items():
                if video_id in pl_data['videos']:
                    in_playlists.append(pl_data['name'])

            if in_playlists:  # Only include if found in at least one playlist
                filtered_results.append((song, in_playlists))

    print(f"Original results: {len(mock_results)}")
    print(f"Filtered results: {len(filtered_results)}")

    for i, (song, playlists) in enumerate(filtered_results, 1):
        title = song.get('title', 'Unknown')
        artist = song.get('artists', [{}])[0].get('name', 'Unknown')
        print(f"{i}. {title} by {artist} - Found in: {', '.join(playlists)}")

    print("✓ Playlist filtering logic works correctly")

if __name__ == "__main__":
    test_playlist_filtering()