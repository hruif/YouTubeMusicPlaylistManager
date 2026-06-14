#!/usr/bin/env python3
"""
Unit tests for UI helper logic that does not require a Tk root window.
"""

from ui import PlaylistManagerUI, PlaylistURLWindow


class FakeBool:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def make_manager():
    manager = PlaylistManagerUI.__new__(PlaylistManagerUI)
    manager.ytmusic = None
    manager.spotapi_available = False
    manager.saved_playlists = {}
    manager.playlists_file = PlaylistManagerUI.PLAYLIST_FILE
    manager.use_display_windows_var = FakeBool(False)
    manager.sidebar_playlist_vars = []
    manager.display_playlist_vars = []
    manager.current_display_view = 'empty'
    manager._active_combined_refresh = None
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
    assert matches['space song beach house']['playlists'] == {'Spotify: Dream Pop'}


def test_collect_combined_tracks_merges_duplicates_across_playlists():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'Morning',
            'videos': {'yt1', 'yt2'},
            'tracks': [
                {
                    'id': 'yt1',
                    'videoId': 'yt1',
                    'title': 'Alpha Song',
                    'artist': 'First Artist',
                    'source': 'youtube'
                },
                {
                    'id': 'yt2',
                    'videoId': 'yt2',
                    'title': 'Beta Song',
                    'artist': 'Second Artist',
                    'source': 'youtube'
                }
            ]
        },
        'spotify:SP1': {
            'source': 'spotify',
            'id': 'SP1',
            'name': 'Evening',
            'videos': {'sp1'},
            'tracks': [
                {
                    'id': 'sp1',
                    'trackId': 'sp1',
                    'title': 'Alpha Song',
                    'artist': 'First Artist',
                    'source': 'spotify'
                }
            ]
        }
    }

    combined = manager._collect_combined_tracks(['youtube:PL1', 'spotify:SP1'])

    assert len(combined) == 2
    alpha_entry = combined[0]
    assert alpha_entry['title'] == 'Alpha Song'
    assert alpha_entry['appearance_count'] == 2
    assert alpha_entry['sources'] == {'youtube', 'spotify'}
    assert alpha_entry['playlists'] == {'Morning', 'Evening'}


def test_collect_combined_tracks_can_keep_duplicate_appearances():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': {'yt1'},
            'tracks': [
                {
                    'id': 'yt1',
                    'videoId': 'yt1',
                    'title': 'Shared Song',
                    'artist': 'Shared Artist',
                    'source': 'youtube'
                }
            ]
        },
        'youtube:PL2': {
            'source': 'youtube',
            'id': 'PL2',
            'name': 'Two',
            'videos': {'yt1'},
            'tracks': [
                {
                    'id': 'yt1',
                    'videoId': 'yt1',
                    'title': 'Shared Song',
                    'artist': 'Shared Artist',
                    'source': 'youtube'
                }
            ]
        }
    }

    combined = manager._collect_combined_tracks(
        ['youtube:PL1', 'youtube:PL2'],
        merge_duplicates=False
    )

    assert len(combined) == 2
    assert [entry['playlists'] for entry in combined] == [{'One'}, {'Two'}]


def test_find_duplicate_entries_only_uses_selected_playlists():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': {'yt1'},
            'tracks': [
                {
                    'id': 'yt1',
                    'videoId': 'yt1',
                    'title': 'Shared Song',
                    'artist': 'Shared Artist',
                    'source': 'youtube'
                }
            ]
        },
        'spotify:SP1': {
            'source': 'spotify',
            'id': 'SP1',
            'name': 'Two',
            'videos': {'sp1'},
            'tracks': [
                {
                    'id': 'sp1',
                    'trackId': 'sp1',
                    'title': 'Shared Song',
                    'artist': 'Shared Artist',
                    'source': 'spotify'
                }
            ]
        },
        'youtube:PL3': {
            'source': 'youtube',
            'id': 'PL3',
            'name': 'Three',
            'videos': {'yt3'},
            'tracks': [
                {
                    'id': 'yt3',
                    'videoId': 'yt3',
                    'title': 'Different Song',
                    'artist': 'Different Artist',
                    'source': 'youtube'
                }
            ]
        }
    }

    unselected_duplicate = manager._find_duplicate_entries(['youtube:PL1', 'youtube:PL3'])
    selected_duplicate = manager._find_duplicate_entries(['youtube:PL1', 'spotify:SP1'])

    assert unselected_duplicate == []
    assert len(selected_duplicate) == 1
    assert selected_duplicate[0]['title'] == 'Shared Song'
    assert selected_duplicate[0]['playlists'] == {'One', 'Two'}


def test_find_duplicate_entries_includes_repeats_inside_one_playlist():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': {'yt1', 'yt2'},
            'tracks': [
                {
                    'id': 'yt1',
                    'videoId': 'yt1',
                    'title': 'Repeated Song',
                    'artist': 'Same Artist',
                    'source': 'youtube'
                },
                {
                    'id': 'yt2',
                    'videoId': 'yt2',
                    'title': 'Repeated Song',
                    'artist': 'Same Artist',
                    'source': 'youtube'
                }
            ]
        }
    }

    duplicates = manager._find_duplicate_entries(['youtube:PL1'])

    assert len(duplicates) == 1
    assert duplicates[0]['title'] == 'Repeated Song'
    assert duplicates[0]['appearance_count'] == 2
    assert duplicates[0]['playlists'] == {'One'}


def test_find_duplicate_songs_allows_one_selected_playlist(monkeypatch):
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': {'yt1', 'yt2'},
            'tracks': [
                {
                    'id': 'yt1',
                    'videoId': 'yt1',
                    'title': 'Repeated Song',
                    'artist': 'Same Artist',
                    'source': 'youtube'
                },
                {
                    'id': 'yt2',
                    'videoId': 'yt2',
                    'title': 'Repeated Song',
                    'artist': 'Same Artist',
                    'source': 'youtube'
                }
            ]
        }
    }
    manager.sidebar_playlist_vars = [('youtube:PL1', FakeBool(True))]
    warnings = []
    shown = []

    monkeypatch.setattr('ui.messagebox.showwarning', lambda title, message: warnings.append((title, message)))
    monkeypatch.setattr(manager, 'show_duplicate_songs_display', lambda duplicates, selected_count: shown.append((duplicates, selected_count)))

    manager.find_duplicate_songs()

    assert warnings == []
    assert len(shown) == 1
    assert shown[0][1] == 1
    assert shown[0][0][0]['title'] == 'Repeated Song'


def test_matches_find_query_requires_all_terms():
    manager = make_manager()

    assert manager._matches_find_query(('Alpha Song', 'First Artist'), 'alpha first')
    assert not manager._matches_find_query(('Alpha Song', 'First Artist'), 'alpha second')


def test_sort_combined_tracks_by_artist_and_original_order():
    manager = make_manager()
    entries = [
        {
            'title': 'Beta',
            'artist': 'Zulu',
            'playlists': {'Second'},
            'sources': {'youtube'},
            'playlist_order': 1,
            'track_order': 0,
            'appearance_count': 1,
            'track': {}
        },
        {
            'title': 'Alpha',
            'artist': 'Alpha',
            'playlists': {'First'},
            'sources': {'youtube'},
            'playlist_order': 0,
            'track_order': 1,
            'appearance_count': 1,
            'track': {}
        }
    ]

    by_artist = manager._sort_combined_tracks(entries, 'Artist (A-Z)')
    original = manager._sort_combined_tracks(entries, 'Original Playlist Order')

    assert [entry['title'] for entry in by_artist] == ['Alpha', 'Beta']
    assert [entry['title'] for entry in original] == ['Alpha', 'Beta']


def test_selected_playlist_keys_use_display_selector_in_window_mode():
    manager = make_manager()
    manager.use_display_windows_var = FakeBool(True)
    manager.sidebar_playlist_vars = [('youtube:PL1', FakeBool(False))]
    manager.display_playlist_vars = [('spotify:SP1', FakeBool(True))]

    assert manager._selected_sidebar_playlist_keys() == ['spotify:SP1']


def test_update_selected_playlists_requires_a_selection(monkeypatch):
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': set(),
            'tracks': []
        }
    }
    manager.sidebar_playlist_vars = [('youtube:PL1', FakeBool(False))]
    warnings = []

    monkeypatch.setattr('ui.messagebox.showwarning', lambda title, message: warnings.append((title, message)))

    manager.update_selected_playlists()

    assert warnings == [('No Selection', 'Please choose at least one playlist to update.')]


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
