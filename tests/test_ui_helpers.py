#!/usr/bin/env python3
"""
Unit tests for UI helper logic that does not require a Tk root window.
"""

from pathlib import Path

from app.services import playlist_store
from app.services.playlist_library import PlaylistLibrary
from app.services.queue_service import QueueService
from app.views.playlist_url_window import PlaylistURLWindow
from app.ui import PlaylistManagerUI


class FakeBool:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeTemporaryPlaylistAccount:
    def __init__(self):
        self.records = []
        self.browser_auth_file = Path("/tmp/nonexistent-ytmusic-browser-auth.json")

    def remember_temporary_playlist(self, playlist_id, title, source_playlists):
        self.records.append((playlist_id, title, source_playlists))

    def has_browser_auth(self):
        return False

    def disconnect_browser_auth(self):
        pass


class FakeTemporaryPlaylistClient:
    def __init__(self, fail_create=False, fail_add=False, failing_video_ids=None, failing_create_video_ids=None):
        self.fail_create = fail_create
        self.fail_add = fail_add
        self.failing_video_ids = set(failing_video_ids or [])
        self.failing_create_video_ids = set(failing_create_video_ids or [])
        self.create_calls = []
        self.add_calls = []
        self.deleted = []

    def create_playlist(self, *args, **kwargs):
        self.create_calls.append((args, kwargs))
        video_ids = set(kwargs.get("video_ids") or [])
        if self.fail_create or self.failing_create_video_ids.intersection(video_ids):
            raise RuntimeError("Server returned HTTP 400: Bad Request.")
        return "TEMP_PLAYLIST"

    def add_playlist_items(self, playlist_id, videoIds=None, duplicates=False):
        video_ids = list(videoIds or [])
        self.add_calls.append((playlist_id, video_ids, duplicates))
        if self.fail_add or any(video_id in self.failing_video_ids for video_id in video_ids):
            return {"status": "STATUS_FAILED"}
        return {"status": "STATUS_SUCCEEDED"}

    def delete_playlist(self, playlist_id):
        self.deleted.append(playlist_id)
        return "STATUS_SUCCEEDED"


def make_manager():
    manager = PlaylistManagerUI.__new__(PlaylistManagerUI)
    manager.ytmusic = None
    manager.spotapi_available = False
    manager.library = PlaylistLibrary(
        PlaylistManagerUI.PLAYLIST_FILE,
        manager._normalize_playlist_entry,
        manager._serialize_playlist_entry,
        manager._playlist_sort_key,
    )
    manager.saved_playlists = {}
    manager.use_display_windows_var = FakeBool(False)
    manager.sidebar_playlist_vars = []
    manager.display_playlist_vars = []
    manager.active_find_entry = None
    manager.current_display_view = 'empty'
    manager._active_combined_refresh = None
    manager.youtube_account = FakeTemporaryPlaylistAccount()
    manager.queue_service = QueueService(
        manager.youtube_account, PlaylistManagerUI.YOUTUBE_TEMP_PLAYLIST_CHUNK_SIZE
    )
    manager.authenticated_ytmusic = None
    manager.browser_authenticated_ytmusic = None
    manager.youtube_queue_auth_error = None
    manager.youtube_queue_headers_verified = False
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

    monkeypatch.setattr('app.ui.messagebox.showwarning', lambda title, message: warnings.append((title, message)))
    monkeypatch.setattr(manager, 'show_duplicate_songs_display', lambda duplicates, selected_count: shown.append((duplicates, selected_count)))

    manager.find_duplicate_songs()

    assert warnings == []
    assert len(shown) == 1
    assert shown[0][1] == 1
    assert shown[0][0][0]['title'] == 'Repeated Song'


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


def test_youtube_playlist_sources_from_keys_filters_spotify():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'YouTube One',
            'videos': set(),
            'tracks': []
        },
        'spotify:SP1': {
            'source': 'spotify',
            'id': 'SP1',
            'name': 'Spotify One',
            'videos': set(),
            'tracks': []
        }
    }

    youtube_playlists, skipped_playlists = playlist_store.select_youtube_playlist_sources(
        manager.saved_playlists,
        ['spotify:SP1', 'youtube:PL1'],
    )

    assert youtube_playlists == [
        {
            'key': 'youtube:PL1',
            'id': 'PL1',
            'name': 'YouTube One',
            'source': 'youtube'
        }
    ]
    assert skipped_playlists == [
        {
            'key': 'spotify:SP1',
            'id': 'SP1',
            'name': 'Spotify One',
            'source': 'spotify'
        }
    ]


def test_temporary_youtube_playlist_creation_uses_cached_video_ids():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': {'fallback1'},
            'tracks': [
                {'videoId': 'video1', 'title': 'One'},
                {'id': 'video2', 'title': 'Two'},
            ]
        },
        'youtube:PL2': {
            'source': 'youtube',
            'id': 'PL2',
            'name': 'Two',
            'videos': {'video3'},
            'tracks': []
        }
    }
    client = FakeTemporaryPlaylistClient()
    statuses = []

    title, playlist_id, skipped = manager._create_temporary_youtube_music_playlist_sync(
        client,
        [
            {'key': 'youtube:PL1', 'id': 'PL1', 'name': 'One', 'source': 'youtube'},
            {'key': 'youtube:PL2', 'id': 'PL2', 'name': 'Two', 'source': 'youtube'},
        ],
        statuses.append,
    )

    assert title.startswith("Playlist Manager Queue")
    assert playlist_id == "TEMP_PLAYLIST"
    assert client.create_calls == [
        (
            (title, "Temporary private playlist created by YouTube Music Playlist Manager."),
            {"privacy_status": "PRIVATE", "video_ids": ["video1"]},
        )
    ]
    assert client.add_calls == [
        ("TEMP_PLAYLIST", ["video2", "video3"], False),
    ]
    assert skipped == []
    assert client.deleted == []
    assert manager.youtube_account.records[0][0] == "TEMP_PLAYLIST"
    assert manager.youtube_account.records[0][2][0]["id"] == "PL1"
    assert statuses[0] == "Creating private playlist with seed song 1 of 3..."


def test_temporary_youtube_playlist_creation_skips_rejected_individual_songs():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': set(),
            'tracks': [
                {'videoId': 'video1'},
                {'videoId': 'bad-video'},
                {'videoId': 'video3'},
            ]
        }
    }
    client = FakeTemporaryPlaylistClient(failing_video_ids={'bad-video'})

    title, playlist_id, skipped = manager._create_temporary_youtube_music_playlist_sync(
        client,
        [{'key': 'youtube:PL1', 'id': 'PL1', 'name': 'One', 'source': 'youtube'}],
        lambda _status: None,
    )

    assert title.startswith("Playlist Manager Queue")
    assert playlist_id == "TEMP_PLAYLIST"
    assert skipped == [{"video_id": "bad-video", "error": "{'status': 'STATUS_FAILED'}"}]
    assert ("TEMP_PLAYLIST", ["bad-video", "video3"], False) in client.add_calls
    assert ("TEMP_PLAYLIST", ["bad-video"], False) in client.add_calls
    assert ("TEMP_PLAYLIST", ["video3"], False) in client.add_calls
    assert client.deleted == []
    assert manager.youtube_account.records[0][0] == "TEMP_PLAYLIST"


def test_temporary_youtube_playlist_creation_retries_rejected_seed_song():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': set(),
            'tracks': [
                {'videoId': 'video1'},
                {'videoId': 'video2'},
            ]
        }
    }
    client = FakeTemporaryPlaylistClient(failing_create_video_ids={'video1'})

    title, playlist_id, skipped = manager._create_temporary_youtube_music_playlist_sync(
        client,
        [{'key': 'youtube:PL1', 'id': 'PL1', 'name': 'One', 'source': 'youtube'}],
        lambda _status: None,
    )

    assert playlist_id == "TEMP_PLAYLIST"
    assert client.create_calls == [
        (
            (title, "Temporary private playlist created by YouTube Music Playlist Manager."),
            {"privacy_status": "PRIVATE", "video_ids": ["video1"]},
        ),
        (
            (title, "Temporary private playlist created by YouTube Music Playlist Manager."),
            {"privacy_status": "PRIVATE", "video_ids": ["video2"]},
        ),
    ]
    assert client.add_calls == [
        ("TEMP_PLAYLIST", ["video1"], False),
    ]
    assert skipped == []
    assert manager.youtube_account.records[0][0] == "TEMP_PLAYLIST"


def test_temporary_youtube_playlist_video_ids_prefer_queue_ok_seed():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': set(),
            'tracks': [
                {
                    'videoId': 'ytm-only',
                    'queueStatus': 'YTM only',
                    'queuePlayable': False,
                    'videoType': 'MUSIC_VIDEO_TYPE_ATV',
                },
                {
                    'videoId': 'queue-ok',
                    'queueStatus': 'Queue OK',
                    'queuePlayable': True,
                    'videoType': 'MUSIC_VIDEO_TYPE_OMV',
                },
            ]
        }
    }

    video_ids = manager._temporary_youtube_playlist_video_ids([
        {'key': 'youtube:PL1', 'id': 'PL1', 'name': 'One', 'source': 'youtube'}
    ])

    assert video_ids == ['queue-ok', 'ytm-only']


def test_temporary_youtube_playlist_video_ids_dedupes_across_playlists():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube', 'id': 'PL1', 'name': 'A', 'videos': set(),
            'tracks': [{'videoId': 'a'}, {'videoId': 'b'}],
        },
        'youtube:PL2': {
            'source': 'youtube', 'id': 'PL2', 'name': 'B', 'videos': set(),
            'tracks': [{'videoId': 'b'}, {'videoId': 'c'}],
        },
    }

    video_ids = manager._temporary_youtube_playlist_video_ids([
        {'key': 'youtube:PL1', 'id': 'PL1', 'name': 'A', 'source': 'youtube'},
        {'key': 'youtube:PL2', 'id': 'PL2', 'name': 'B', 'source': 'youtube'},
    ])

    # 'b' appears in both playlists but must only be sent once.
    assert video_ids == ['a', 'b', 'c']


def test_summarize_skip_reasons_lists_distinct_reasons():
    manager = make_manager()
    skipped = [
        {'video_id': 'x', 'error': 'HTTP 409: already in playlist'},
        {'video_id': 'y', 'error': 'HTTP 409: already in playlist'},
        {'video_id': 'z', 'error': 'HTTP 400: unavailable'},
    ]

    assert manager._summarize_skip_reasons(skipped) == (
        'HTTP 409: already in playlist | HTTP 400: unavailable'
    )
    assert manager._summarize_skip_reasons([]) == ''


def test_temporary_youtube_playlist_creation_reports_create_failure():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL1': {
            'source': 'youtube',
            'id': 'PL1',
            'name': 'One',
            'videos': set(),
            'tracks': [
                {'videoId': 'video1'},
                {'videoId': 'video2'},
            ]
        }
    }
    client = FakeTemporaryPlaylistClient(fail_create=True)

    try:
        manager._create_temporary_youtube_music_playlist_sync(
            client,
            [{'key': 'youtube:PL1', 'id': 'PL1', 'name': 'One', 'source': 'youtube'}],
            lambda _status: None,
        )
    except RuntimeError as error:
        assert "Could not create the temporary playlist" in str(error)
        assert "browser auth" in str(error)
    else:
        raise AssertionError("Temporary playlist creation should fail when every seed song is rejected")

    assert client.deleted == []
    assert manager.youtube_account.records == []


def test_temporary_youtube_playlist_creation_requires_cached_video_ids():
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
    client = FakeTemporaryPlaylistClient()

    try:
        manager._create_temporary_youtube_music_playlist_sync(
            client,
            [{'key': 'youtube:PL1', 'id': 'PL1', 'name': 'One', 'source': 'youtube'}],
            lambda _status: None,
        )
    except RuntimeError as error:
        assert "No cached YouTube songs" in str(error)
    else:
        raise AssertionError("Temporary playlist creation should require cached song ids")

    assert client.create_calls == []


def test_youtube_queue_auth_status_reports_failed_saved_headers():
    manager = make_manager()
    manager.youtube_queue_auth_error = "bad headers"
    manager.browser_authenticated_ytmusic = object()

    assert not manager._is_youtube_music_queue_connected()
    assert manager._youtube_music_queue_auth_status() == "Saved browser headers failed, refresh needed"


def test_format_browser_auth_test_error_explains_json_decode_failure():
    manager = make_manager()

    message = manager._format_browser_auth_test_error("Expecting value: line 1 column 1 (char 0)")

    assert "POST /browse" in message
    assert "Copy as fetch" in message


def test_format_youtube_oauth_error_mentions_tv_client_for_bad_client():
    manager = make_manager()

    message = manager._format_youtube_oauth_error(
        "OAuth client failure. Most likely client_id and client_secret mismatch or YouTubeData API is not enabled."
    )

    assert "TVs and Limited Input devices" in message
    assert "Desktop OAuth clients will fail" in message


def test_format_youtube_oauth_error_mentions_test_users_for_access_denied():
    manager = make_manager()

    message = manager._format_youtube_oauth_error("Error 403: access_denied")

    assert "Audience" in message
    assert "Test users" in message


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

    monkeypatch.setattr('app.ui.messagebox.showwarning', lambda title, message: warnings.append((title, message)))

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
    auto_window = make_url_window('auto')

    assert youtube_window._extract_playlist_id(
        'https://music.youtube.com/playlist?list=PLabc_123-extra'
    ) == 'PLabc_123-extra'
    assert spotify_window._extract_playlist_id(
        'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc'
    ) == '37i9dQZF1DXcBWIGoYBM5M'
    assert auto_window._detect_source(
        'https://music.youtube.com/playlist?list=PLabc_123-extra'
    ) == 'youtube'
    assert auto_window._detect_source(
        'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc'
    ) == 'spotify'
    assert auto_window._extract_playlist_id(
        'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc'
    ) == '37i9dQZF1DXcBWIGoYBM5M'


def test_sorted_playlist_items_orders_by_name_then_source():
    manager = make_manager()
    manager.saved_playlists = {
        'youtube:PL2': {'source': 'youtube', 'id': 'PL2', 'name': 'Zulu'},
        'spotify:SP1': {'source': 'spotify', 'id': 'SP1', 'name': 'Alpha'},
        'youtube:PL1': {'source': 'youtube', 'id': 'PL1', 'name': 'Alpha'},
    }

    assert [key for key, _ in manager._sorted_playlist_items()] == [
        'spotify:SP1',
        'youtube:PL1',
        'youtube:PL2'
    ]
