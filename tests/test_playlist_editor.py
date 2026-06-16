#!/usr/bin/env python3
"""Tests for the pure logic + network calls in `app.services.playlist_editor`
(the add/remove-songs-from-YouTube-playlists feature)."""

import pytest

from app.services import playlist_editor
from app.services.playlist_editor import PlaylistEditor


def test_find_set_video_ids_matches_all_occurrences():
    response = {
        "tracks": [
            {"videoId": "AAA", "setVideoId": "set-aaa-1"},
            {"videoId": "BBB", "setVideoId": "set-bbb"},
            {"videoId": "AAA", "setVideoId": "set-aaa-2"},  # duplicate song
            {"videoId": "AAA"},                              # no setVideoId -> skipped
            "not-a-dict",
        ]
    }
    assert playlist_editor.find_set_video_ids(response, "AAA") == ["set-aaa-1", "set-aaa-2"]
    assert playlist_editor.find_set_video_ids(response, "ZZZ") == []
    assert playlist_editor.find_set_video_ids(None, "AAA") == []


def test_addable_targets_excludes_spotify_and_playlists_already_containing_song():
    saved = {
        "youtube:PL_has": {"source": "youtube", "id": "PL_has", "name": "Has It",
                            "videos": {"VID"}, "tracks": []},
        "youtube:PL_b": {"source": "youtube", "id": "PL_b", "name": "Beta",
                         "videos": set(), "tracks": []},
        "youtube:PL_a": {"source": "youtube", "id": "PL_a", "name": "alpha",
                         "videos": set(), "tracks": []},
        "spotify:abc": {"source": "spotify", "id": "abc", "name": "Spotify One",
                        "videos": set(), "tracks": []},
        "youtube:no_id": {"source": "youtube", "id": "", "name": "No Id",
                          "videos": set(), "tracks": []},
    }
    targets = playlist_editor.addable_target_playlists(saved, "VID")
    # Sorted case-insensitively by name; excludes the one that has VID, Spotify, and the id-less one.
    assert [t["name"] for t in targets] == ["alpha", "Beta"]
    assert [t["key"] for t in targets] == ["youtube:PL_a", "youtube:PL_b"]


def test_playlist_contains_video_checks_videos_set_and_tracks():
    assert playlist_editor.playlist_contains_video({"videos": {"VID"}}, "VID")
    assert playlist_editor.playlist_contains_video({"videos": ["VID"]}, "VID")
    assert playlist_editor.playlist_contains_video({"tracks": [{"videoId": "VID"}]}, "VID")
    assert playlist_editor.playlist_contains_video({"tracks": [{"id": "VID"}]}, "VID")
    assert not playlist_editor.playlist_contains_video({"videos": set(), "tracks": []}, "VID")


def test_apply_local_add_updates_videos_and_tracks_without_duplicating():
    pl = {"videos": {"OLD"}, "tracks": [{"videoId": "OLD", "title": "Old"}]}
    playlist_editor.apply_local_add(pl, {"videoId": "NEW", "title": "New"}, "NEW")
    assert pl["videos"] == {"OLD", "NEW"}
    assert {t["videoId"] for t in pl["tracks"]} == {"OLD", "NEW"}

    # Adding the same video again does not append a second track row.
    playlist_editor.apply_local_add(pl, {"videoId": "NEW", "title": "New"}, "NEW")
    assert len(pl["tracks"]) == 2


def test_apply_local_remove_drops_video_from_set_and_tracks():
    pl = {"videos": {"A", "B"}, "tracks": [{"videoId": "A"}, {"videoId": "B"}, {"id": "A"}]}
    playlist_editor.apply_local_remove(pl, "A")
    assert pl["videos"] == {"B"}
    assert [playlist_editor._track_video_id(t) for t in pl["tracks"]] == ["B"]


class FakeClient:
    def __init__(self, playlist=None, add_response="STATUS_SUCCEEDED", remove_response="STATUS_SUCCEEDED"):
        self._playlist = playlist or {"tracks": []}
        self._add_response = add_response
        self._remove_response = remove_response
        self.added = None
        self.removed = None

    def add_playlist_items(self, playlist_id, videoIds=None, duplicates=False):
        self.added = (playlist_id, videoIds, duplicates)
        return self._add_response

    def get_playlist(self, playlist_id, limit=None):
        return self._playlist

    def remove_playlist_items(self, playlist_id, videos):
        self.removed = (playlist_id, videos)
        return self._remove_response


def test_add_song_calls_client_and_returns_on_success():
    client = FakeClient(add_response={"status": "STATUS_SUCCEEDED"})
    editor = PlaylistEditor()
    editor.add_song(client, "PL1", "VID")
    assert client.added == ("PL1", ["VID"], False)


def test_add_song_raises_when_not_confirmed():
    client = FakeClient(add_response={"status": "STATUS_FAILED"})
    with pytest.raises(RuntimeError):
        PlaylistEditor().add_song(client, "PL1", "VID")


def test_remove_song_looks_up_set_video_id_then_removes():
    client = FakeClient(playlist={"tracks": [{"videoId": "VID", "setVideoId": "SET1"}]})
    PlaylistEditor().remove_song(client, "PL1", "VID")
    assert client.removed == ("PL1", [{"videoId": "VID", "setVideoId": "SET1"}])


def test_remove_song_raises_when_song_absent():
    client = FakeClient(playlist={"tracks": [{"videoId": "OTHER", "setVideoId": "SET"}]})
    with pytest.raises(RuntimeError, match="not found"):
        PlaylistEditor().remove_song(client, "PL1", "VID")
