#!/usr/bin/env python3
"""
Unit tests for UI helper logic that does not require a Tk root window.
"""

from playlist_url_window import PlaylistURLWindow
from ui import PlaylistManagerUI


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
    manager.active_find_entry = None
    manager.current_display_view = 'empty'
    manager._active_combined_refresh = None
    manager.youtube_player = None
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


def test_extract_playlist_name_uses_direct_and_renderer_titles():
    manager = make_manager()

    assert manager._extract_playlist_name({'title': 'Direct Title'}) == 'Direct Title'
    assert manager._extract_playlist_name({
        'header': {
            'musicResponsiveHeaderRenderer': {
                'title': {'runs': [{'text': 'Renderer Title'}]}
            }
        }
    }) == 'Renderer Title'


def test_extract_track_metadata_keeps_playback_markers_and_thumbnail():
    manager = make_manager()

    video_ids, tracks = manager._extract_track_metadata({
        'tracks': [
            {
                'videoId': 'yt1',
                'title': 'Audio Track',
                'artists': [{'name': 'Artist'}],
                'videoType': 'MUSIC_VIDEO_TYPE_ATV',
                'isAvailable': True,
                'thumbnails': [
                    {'url': 'small.jpg', 'width': 60, 'height': 60},
                    {'url': 'large.jpg', 'width': 120, 'height': 120}
                ]
            }
        ]
    })

    assert video_ids == {'yt1'}
    assert tracks[0]['videoType'] == 'MUSIC_VIDEO_TYPE_ATV'
    assert tracks[0]['isAvailable'] is True
    assert tracks[0]['thumbnailUrl'] == 'large.jpg'
    assert tracks[0]['queueStatus'] == 'YTM only'
    assert tracks[0]['queuePlayable'] is False


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


def test_serialize_playlist_entry_normalizes_sets_and_track_ids():
    manager = make_manager()

    serialized = manager._serialize_playlist_entry(
        'spotify:SP123',
        {
            'source': 'spotify',
            'id': 'spotify:SP123',
            'name': 'Saved Spotify',
            'videos': {'track2', 'track1'},
            'tracks': [
                {
                    'id': 'spotify:track:track1',
                    'name': 'Ignored Name',
                    'title': 'Track One',
                    'artist': 'Artist One'
                }
            ]
        }
    )

    assert serialized == {
        'source': 'spotify',
        'id': 'SP123',
        'name': 'Saved Spotify',
        'videos': ['track1', 'track2'],
        'tracks': [
            {
                'id': 'track1',
                'name': 'Ignored Name',
                'title': 'Track One',
                'artist': 'Artist One',
                'source': 'spotify',
                'trackId': 'track1'
            }
        ]
    }


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
    assert manager._entry_playlist_occurrence_labels(alpha_entry) == ['YouTube: Morning', 'Spotify: Evening']


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
    assert manager._entry_playlist_occurrence_labels(duplicates[0]) == ['YouTube: One (2)']
    assert manager._entry_playlist_occurrence_summaries(duplicates[0]) == [
        {
            'label': 'YouTube: One',
            'count': 2,
            'track_ids': ['yt1', 'yt2'],
            'urls': [
                'https://music.youtube.com/watch?v=yt1',
                'https://music.youtube.com/watch?v=yt2'
            ]
        }
    ]


def test_playlist_occurrence_format_truncates_long_display():
    manager = make_manager()
    entry = {
        'appearances': [
            {'source': 'youtube', 'playlist': 'A Very Long Playlist Name', 'track': {}},
            {'source': 'spotify', 'playlist': 'Another Very Long Playlist Name', 'track': {}}
        ]
    }

    formatted = manager._format_playlist_occurrences(entry, limit=30)

    assert len(formatted) <= 30
    assert formatted.endswith('...')


def test_entry_play_url_prefers_youtube_music():
    manager = make_manager()
    entry = {
        'appearances': [
            {
                'source': 'spotify',
                'playlist': 'Spotify List',
                'track': {'id': 'sp1', 'trackId': 'sp1'}
            },
            {
                'source': 'youtube',
                'playlist': 'YouTube List',
                'track': {'id': 'yt1', 'videoId': 'yt1'}
            }
        ]
    }

    assert manager._entry_play_url(entry) == 'https://music.youtube.com/watch?v=yt1'


def test_track_play_url_handles_spotify_uri():
    manager = make_manager()

    assert (
        manager._track_play_url('spotify', {'id': 'spotify:track:abc123'})
        == 'https://open.spotify.com/track/abc123'
    )


def test_youtube_queue_actions_are_hidden_without_opt_in(monkeypatch):
    manager = make_manager()

    monkeypatch.delenv(PlaylistManagerUI.YOUTUBE_QUEUE_ACTIONS_ENV_VAR, raising=False)
    assert not manager._show_youtube_queue_actions()

    monkeypatch.setenv(PlaylistManagerUI.YOUTUBE_QUEUE_ACTIONS_ENV_VAR, '1')
    assert manager._show_youtube_queue_actions()


def test_playlist_url_builds_source_links():
    manager = make_manager()

    assert manager._playlist_url('youtube', 'PL123') == 'https://music.youtube.com/playlist?list=PL123'
    assert manager._playlist_url('spotify', 'SP123') == 'https://open.spotify.com/playlist/SP123'


def test_cached_track_id_count_ignores_duplicate_ids():
    manager = make_manager()

    assert manager._cached_track_id_count([
        {'id': 'one'},
        {'trackId': 'one'},
        {'videoId': 'two'},
        {'title': 'No ID'}
    ]) == 2


def test_youtube_queue_tracks_from_entries_prefers_youtube_and_filters_spotify():
    manager = make_manager()
    entries = [
        {
            'title': 'Shared Song',
            'artist': 'Shared Artist',
            'playlists': {'Spotify List', 'YouTube List'},
            'appearances': [
                {
                    'source': 'spotify',
                    'playlist': 'Spotify List',
                    'track': {'id': 'sp1', 'trackId': 'sp1', 'title': 'Shared Song'}
                },
                {
                    'source': 'youtube',
                    'playlist': 'YouTube List',
                    'track': {
                        'id': 'yt1',
                        'videoId': 'yt1',
                        'title': 'Shared Song',
                        'videoType': 'MUSIC_VIDEO_TYPE_OMV',
                        'thumbnailUrl': 'https://example.com/thumb.jpg'
                    }
                }
            ]
        },
        {
            'title': 'Spotify Only',
            'artist': 'Spotify Artist',
            'playlists': {'Spotify List'},
            'appearances': [
                {
                    'source': 'spotify',
                    'playlist': 'Spotify List',
                    'track': {'id': 'sp2', 'trackId': 'sp2', 'title': 'Spotify Only'}
                }
            ]
        }
    ]

    queue_tracks = manager._youtube_queue_tracks_from_entries(entries)

    assert queue_tracks == [
        {
            'videoId': 'yt1',
            'title': 'Shared Song',
            'artist': 'Shared Artist',
            'playlist': 'YouTube: YouTube List',
            'sourceUrl': 'https://music.youtube.com/watch?v=yt1',
            'thumbnailUrl': 'https://example.com/thumb.jpg',
            'playbackStatus': 'Queue OK'
        }
    ]


def test_youtube_queue_tracks_skip_youtube_music_only_tracks():
    manager = make_manager()
    entries = [
        {
            'title': 'Audio Track',
            'artist': 'Artist',
            'playlists': {'YouTube List'},
            'appearances': [
                {
                    'source': 'youtube',
                    'playlist': 'YouTube List',
                    'track': {
                        'id': 'yt1',
                        'videoId': 'yt1',
                        'title': 'Audio Track',
                        'videoType': 'MUSIC_VIDEO_TYPE_ATV'
                    }
                }
            ]
        },
        {
            'title': 'Video Track',
            'artist': 'Artist',
            'playlists': {'YouTube List'},
            'appearances': [
                {
                    'source': 'youtube',
                    'playlist': 'YouTube List',
                    'track': {
                        'id': 'yt2',
                        'videoId': 'yt2',
                        'title': 'Video Track',
                        'videoType': 'MUSIC_VIDEO_TYPE_OMV'
                    }
                }
            ]
        }
    ]

    assert manager._entry_queue_status(entries[0]) == 'YTM only'
    assert [track['videoId'] for track in manager._youtube_queue_tracks_from_entries(entries)] == ['yt2']


def test_youtube_queue_tracks_skip_persisted_unavailable_tracks():
    manager = make_manager()
    entries = [
        {
            'title': 'Unavailable Track',
            'artist': 'Artist',
            'appearances': [
                {
                    'source': 'youtube',
                    'playlist': 'YouTube List',
                    'track': {
                        'id': 'yt1',
                        'videoId': 'yt1',
                        'title': 'Unavailable Track',
                        'queueStatus': 'Unavailable',
                        'queuePlayable': False
                    }
                }
            ]
        },
        {
            'title': 'Playable Track',
            'artist': 'Artist',
            'appearances': [
                {
                    'source': 'youtube',
                    'playlist': 'YouTube List',
                    'track': {
                        'id': 'yt2',
                        'videoId': 'yt2',
                        'title': 'Playable Track',
                        'queueStatus': 'Queue OK',
                        'queuePlayable': True
                    }
                }
            ]
        }
    ]

    assert manager._entry_queue_status(entries[0]) == 'Unavailable'
    assert [track['videoId'] for track in manager._youtube_queue_tracks_from_entries(entries)] == ['yt2']


def test_youtube_queue_tracks_from_entries_deduplicates_video_ids():
    manager = make_manager()
    entries = [
        {
            'title': 'First',
            'artist': 'Artist',
            'appearances': [
                {'source': 'youtube', 'playlist': 'One', 'track': {'id': 'yt1', 'videoId': 'yt1'}}
            ]
        },
        {
            'title': 'First Again',
            'artist': 'Artist',
            'appearances': [
                {'source': 'youtube', 'playlist': 'Two', 'track': {'id': 'yt1', 'videoId': 'yt1'}}
            ]
        }
    ]

    assert len(manager._youtube_queue_tracks_from_entries(entries)) == 1


def test_youtube_queue_tracks_from_playlist_only_supports_youtube():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'YouTube Playlist',
            'videos': {'yt1'},
            'tracks': [
                {
                    'id': 'yt1',
                    'videoId': 'yt1',
                    'title': 'YouTube Song',
                    'artist': 'YouTube Artist',
                    'source': 'youtube',
                    'videoType': 'MUSIC_VIDEO_TYPE_OMV'
                }
            ]
        },
        'spotify:SP1': {
            'source': 'spotify',
            'id': 'SP1',
            'name': 'Spotify Playlist',
            'videos': {'sp1'},
            'tracks': [
                {
                    'id': 'sp1',
                    'trackId': 'sp1',
                    'title': 'Spotify Song',
                    'artist': 'Spotify Artist',
                    'source': 'spotify'
                }
            ]
        }
    }

    assert manager._youtube_queue_tracks_from_playlist('spotify:SP1') == []
    assert manager._youtube_queue_tracks_from_playlist('youtube:PL1') == [
        {
            'videoId': 'yt1',
            'title': 'YouTube Song',
            'artist': 'YouTube Artist',
            'playlist': 'YouTube: YouTube Playlist',
            'sourceUrl': 'https://music.youtube.com/watch?v=yt1',
            'thumbnailUrl': None,
            'playbackStatus': 'Queue OK'
        }
    ]


def test_player_unavailable_report_persists_queue_marker(monkeypatch):
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
                    'title': 'Unavailable Track',
                    'artist': 'Artist',
                    'source': 'youtube'
                }
            ]
        }
    }
    saved = []
    refreshed = []

    monkeypatch.setattr(manager, 'save_playlists', lambda: saved.append(True))
    monkeypatch.setattr(manager, '_refresh_live_combined_if_active', lambda: refreshed.append(True))

    manager._apply_youtube_track_unavailable({'videoId': 'yt1', 'errorCode': 150})

    track = manager.saved_playlists['youtube:PL1']['tracks'][0]
    assert track['queueStatus'] == 'Unavailable'
    assert track['queuePlayable'] is False
    assert track['queueUnavailableReason'] == 'iframe error 150'
    assert manager._youtube_queue_tracks_from_playlist('youtube:PL1') == []
    assert saved == [True]
    assert refreshed == [True]


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
