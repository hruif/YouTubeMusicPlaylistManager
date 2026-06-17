#!/usr/bin/env python3
"""Tests for the removed-songs archive: diff detection + persistent store."""

from app.services import removed_songs
from app.services.removed_songs import RemovedSongsStore


def test_diff_removed_tracks_finds_tracks_absent_from_new_set():
    old = [
        {"videoId": "A", "title": "Keep", "artist": "X"},
        {"videoId": "B", "title": "Gone", "artist": "Y"},
        {"id": "C", "title": "AlsoGone", "artist": "Z"},
    ]
    new = [{"videoId": "A", "title": "Keep", "artist": "X"}]
    removed = removed_songs.diff_removed_tracks(old, new)
    assert [r.get("videoId") or r.get("id") for r in removed] == ["B", "C"]


def test_diff_ignores_tracks_without_identity_and_handles_empties():
    assert removed_songs.diff_removed_tracks([], [{"videoId": "A"}]) == []
    assert removed_songs.diff_removed_tracks([{"title": "no id"}], []) == []  # no identity -> skipped


def test_store_records_dedupes_and_persists(tmp_path):
    path = tmp_path / "removed.json"
    store = RemovedSongsStore(store_file=path)

    added = store.record("youtube:PL1", "My Playlist",
                         [{"videoId": "B", "title": "Gone", "artist": "Y", "source": "youtube"}],
                         removed_at=1000)
    assert added == 1
    songs = store.for_playlist("youtube:PL1")
    assert len(songs) == 1
    assert songs[0]["title"] == "Gone" and songs[0]["artist"] == "Y"
    assert songs[0]["removed_at"] == 1000

    # Recording the same song id again does not duplicate it.
    assert store.record("youtube:PL1", "My Playlist",
                        [{"videoId": "B", "title": "Gone", "artist": "Y"}], removed_at=2000) == 0
    assert len(store.for_playlist("youtube:PL1")) == 1

    # Persists across instances.
    reloaded = RemovedSongsStore(store_file=path)
    assert [s["title"] for s in reloaded.for_playlist("youtube:PL1")] == ["Gone"]


def test_store_record_no_tracks_is_noop_and_clear_removes(tmp_path):
    store = RemovedSongsStore(store_file=tmp_path / "removed.json")
    assert store.record("youtube:PL1", "P", [], removed_at=1) == 0
    assert store.for_playlist("youtube:PL1") == []

    store.record("youtube:PL1", "P", [{"videoId": "B", "title": "G", "artist": "Y"}], removed_at=1)
    store.clear("youtube:PL1")
    assert store.for_playlist("youtube:PL1") == []
