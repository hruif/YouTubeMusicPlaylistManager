#!/usr/bin/env python3
"""Tests for the persisted per-playlist unmatched-songs store (Spotify transfer)."""

from app.services.unmatched_songs import UnmatchedSongsStore


def test_set_dedupes_and_drops_titleless(tmp_path):
    store = UnmatchedSongsStore(store_file=tmp_path / "u.json")
    store.set("youtube:PL1", [
        {"title": "Song A", "artist": "X"},
        {"title": "song a", "artist": "x"},   # dup (case-insensitive) -> dropped
        {"title": "", "artist": "No Title"},   # no title -> dropped
        {"title": "Song B", "artist": "Y"},
    ])
    got = store.for_playlist("youtube:PL1")
    assert got == [{"title": "Song A", "artist": "X"}, {"title": "Song B", "artist": "Y"}]


def test_persists_across_instances_and_clear(tmp_path):
    path = tmp_path / "u.json"
    UnmatchedSongsStore(store_file=path).set("youtube:PL1", [{"title": "T", "artist": "A"}])
    assert UnmatchedSongsStore(store_file=path).for_playlist("youtube:PL1") == [{"title": "T", "artist": "A"}]

    store = UnmatchedSongsStore(store_file=path)
    store.set("youtube:PL1", [])  # empty clears it
    assert store.for_playlist("youtube:PL1") == []
    assert UnmatchedSongsStore(store_file=path).for_playlist("youtube:PL1") == []


def test_for_playlist_unknown_key_is_empty(tmp_path):
    assert UnmatchedSongsStore(store_file=tmp_path / "u.json").for_playlist("nope") == []
