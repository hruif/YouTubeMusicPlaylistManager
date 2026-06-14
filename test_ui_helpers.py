#!/usr/bin/env python3
"""
Unit tests for UI helper logic that does not require a Tk root window.
"""

from ui import PlaylistManagerUI, PlaylistURLWindow


def make_manager():
    manager = PlaylistManagerUI.__new__(PlaylistManagerUI)
    manager.ytmusic = None
    manager.spotapi_available = False
    manager.saved_playlists = {}
    manager.playlists_file = PlaylistManagerUI.PLAYLIST_FILE
    return manager


def make_url_window(source):
    window = PlaylistURLWindow.__new__(PlaylistURLWindow)
    window.source = source
    return window


def test_extract_playlist_name_handles_rich_header_title():
    manager = make_manager()
    playlist = {
        'header': {
            'title': {
                'runs': [{'text': 'Nested Playlist Title'}]
            }
        }
    }

    assert manager._extract_playlist_name(playlist) == 'Nested Playlist Title'


def test_normalize_legacy_playlist_entry_without_youtube_client():
    manager = make_manager()
    entry = manager._normalize_playlist_entry(
        'PL123',
        {
            'name': 'Legacy Playlist',
            'videos': ['vid2', 'vid1']
        }
    )

    assert entry['source'] == 'youtube'
    assert entry['id'] == 'PL123'
    assert entry['videos'] == {'vid1', 'vid2'}
    assert [track['videoId'] for track in entry['tracks']] == ['vid1', 'vid2']


def test_find_matching_tracks_uses_cached_data_only():
    manager = make_manager()
    manager.saved_playlists = {
        'spotify:SP123': {
            'source': 'spotify',
            'id': 'SP123',
            'name': 'Dream Pop',
            'videos': {'track1'},
            'tracks': [
                {
                    'id': 'track1',
                    'trackId': 'track1',
                    'title': 'Space Song',
                    'artist': 'Beach House',
                    'source': 'spotify'
                }
            ]
        }
    }

    matches = manager._find_matching_tracks('space beach')

    assert list(matches) == ['space song beach house']
    assert matches['space song beach house']['playlists'] == {'🎵 Dream Pop'}


def test_extract_spotify_track_handles_uri_and_profile_artist():
    manager = make_manager()
    track = manager._extract_spotify_track_from_item({
        'track': {
            'uri': 'spotify:track:abc123',
            'name': 'Synthetic Track',
            'artists': [{'profile': {'name': 'Synthetic Artist'}}]
        }
    })

    assert track == {
        'id': 'abc123',
        'trackId': 'abc123',
        'title': 'Synthetic Track',
        'artist': 'Synthetic Artist',
        'source': 'spotify'
    }


def test_extract_spotify_items_accepts_single_item_page():
    manager = make_manager()
    item = {
        'track': {
            'id': 'track1',
            'name': 'Track One'
        }
    }

    assert manager._extract_spotify_items_from_page(item) == [item]


def test_playlist_url_parsing_for_youtube_and_spotify():
    youtube_window = make_url_window('youtube')
    spotify_window = make_url_window('spotify')

    assert youtube_window._extract_playlist_id(
        'https://music.youtube.com/playlist?list=PLabc_123-extra'
    ) == 'PLabc_123-extra'
    assert spotify_window._extract_playlist_id(
        'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc'
    ) == '37i9dQZF1DXcBWIGoYBM5M'
