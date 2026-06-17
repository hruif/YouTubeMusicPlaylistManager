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


def test_find_repeat_items_returns_extra_occurrences_keeping_first():
    playlist = {
        "tracks": [
            {"videoId": "A", "setVideoId": "a1"},   # first A -> kept
            {"videoId": "B", "setVideoId": "b1"},   # only B -> kept
            {"videoId": "A", "setVideoId": "a2"},   # extra A -> remove
            {"videoId": "A", "setVideoId": "a3"},   # extra A -> remove
            {"videoId": "C"},                         # no setVideoId -> ignored
        ]
    }
    extras = playlist_editor.find_repeat_items(playlist)
    assert extras == [
        {"videoId": "A", "setVideoId": "a2"},
        {"videoId": "A", "setVideoId": "a3"},
    ]
    assert playlist_editor.find_repeat_items({"tracks": []}) == []


def test_dedupe_local_tracks_keeps_first_per_id():
    pl = {"tracks": [
        {"videoId": "A", "title": "first"},
        {"videoId": "B"},
        {"videoId": "A", "title": "dup"},
        {"title": "no id keeps"},
    ]}
    playlist_editor.dedupe_local_tracks(pl)
    assert [t.get("videoId") or t.get("title") for t in pl["tracks"]] == ["A", "B", "no id keeps"]


def test_add_songs_dedupes_and_calls_once():
    client = FakeClient()
    n = PlaylistEditor().add_songs(client, "PL1", ["A", "B", "A", "", None, "C"])
    assert n == 3
    assert client.added == ("PL1", ["A", "B", "C"], False)


def test_add_songs_empty_is_noop():
    client = FakeClient()
    assert PlaylistEditor().add_songs(client, "PL1", []) == 0
    assert client.added is None


def test_remove_songs_collects_all_matching_set_video_ids():
    client = FakeClient(playlist={"tracks": [
        {"videoId": "A", "setVideoId": "a1"},
        {"videoId": "B", "setVideoId": "b1"},
        {"videoId": "A", "setVideoId": "a2"},   # A appears twice -> both removed
        {"videoId": "C", "setVideoId": "c1"},   # not requested -> kept
    ]})
    n = PlaylistEditor().remove_songs(client, "PL1", ["A", "B"])
    assert n == 3
    assert client.removed == ("PL1", [
        {"videoId": "A", "setVideoId": "a1"},
        {"videoId": "B", "setVideoId": "b1"},
        {"videoId": "A", "setVideoId": "a2"},
    ])


def test_remove_songs_noop_when_none_present():
    client = FakeClient(playlist={"tracks": [{"videoId": "Z", "setVideoId": "z1"}]})
    assert PlaylistEditor().remove_songs(client, "PL1", ["A", "B"]) == 0
    assert client.removed is None


def test_remove_repeats_removes_extras_and_returns_count():
    client = FakeClient(playlist={"tracks": [
        {"videoId": "A", "setVideoId": "a1"},
        {"videoId": "A", "setVideoId": "a2"},
    ]})
    count = PlaylistEditor().remove_repeats(client, "PL1")
    assert count == 1
    assert client.removed == ("PL1", [{"videoId": "A", "setVideoId": "a2"}])


def test_remove_repeats_noop_when_no_duplicates():
    client = FakeClient(playlist={"tracks": [{"videoId": "A", "setVideoId": "a1"}]})
    assert PlaylistEditor().remove_repeats(client, "PL1") == 0
    assert client.removed is None  # never called remove


def test_edit_on_unowned_playlist_when_signed_in_says_not_yours():
    # Signed in, but the playlist is genuinely someone else's (owned=False).
    unowned = {"owned": False, "author": {"name": "Someone Else"},
               "tracks": [{"videoId": "A"}, {"videoId": "A"}]}
    client = FakeClient(playlist=unowned, authenticated=True)
    with pytest.raises(RuntimeError, match="Someone Else"):
        PlaylistEditor().remove_repeats(client, "PL1")
    assert client.removed is None


def test_edit_on_unowned_playlist_when_signed_out_says_session_expired():
    # Stale session: reads public data but isn't signed in -> own playlists look unowned.
    unowned = {"owned": False, "author": {"name": "Me"},
               "tracks": [{"videoId": "A"}, {"videoId": "A"}]}
    client = FakeClient(playlist=unowned, authenticated=False)
    with pytest.raises(RuntimeError, match="no longer signed in"):
        PlaylistEditor().remove_repeats(client, "PL1")
    with pytest.raises(RuntimeError, match="no longer signed in"):
        PlaylistEditor().remove_song(client, "PL1", "A")
    assert client.removed is None


class FakeClient:
    def __init__(self, playlist=None, add_response="STATUS_SUCCEEDED", remove_response="STATUS_SUCCEEDED",
                 authenticated=True):
        self._playlist = playlist or {"tracks": []}
        self._add_response = add_response
        self._remove_response = remove_response
        self._authenticated = authenticated
        self.added = None
        self.removed = None

    def add_playlist_items(self, playlist_id, videoIds=None, duplicates=False):
        self.added = (playlist_id, videoIds, duplicates)
        return self._add_response

    def get_playlist(self, playlist_id, limit=None):
        return self._playlist

    def get_account_info(self):
        if not self._authenticated:
            raise KeyError("no signed-in account")  # mimics ytmusicapi on a stale session
        return {"accountName": "Me"}

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
