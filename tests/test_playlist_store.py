#!/usr/bin/env python3
"""Tests for the pure playlist identity/key helpers in playlist_store."""

from app.services import playlist_store as ps


def test_normalize_song_key_strips_case_and_punctuation():
    assert ps.normalize_song_key("Hello, World!", "The Band") == "hello world the band"
    assert ps.normalize_song_key("", "") == ""
    assert ps.normalize_song_key(None, None) == ""


def test_playlist_storage_key_joins_source_and_id():
    assert ps.playlist_storage_key("youtube", "PL1") == "youtube:PL1"


def test_split_storage_key_recognizes_known_sources():
    assert ps.split_storage_key("spotify:ABC") == ("spotify", "ABC")
    assert ps.split_storage_key("youtube:XYZ") == ("youtube", "XYZ")
    # Unknown prefix or bare id falls back to youtube with the whole key as id.
    assert ps.split_storage_key("PLbareid") == ("youtube", "PLbareid")
    assert ps.split_storage_key("vimeo:123") == ("youtube", "vimeo:123")


def test_normalize_playlist_identity_prefers_data_then_key():
    # pl_data wins when it carries a valid source/id.
    assert ps.normalize_playlist_identity("youtube:PL1", {"source": "spotify", "id": "SP1"}) == (
        "spotify",
        "SP1",
    )
    # Falls back to the stored key when pl_data is empty.
    assert ps.normalize_playlist_identity("spotify:SP9", {}) == ("spotify", "SP9")
    # Strips a redundant "source:" prefix embedded in the id.
    assert ps.normalize_playlist_identity("youtube:PL1", {"id": "youtube:PL1"}) == (
        "youtube",
        "PL1",
    )
    # Invalid source in pl_data is ignored in favor of the stored source.
    assert ps.normalize_playlist_identity("spotify:SP9", {"source": "vimeo"}) == ("spotify", "SP9")


def test_select_youtube_playlist_sources_splits_by_source():
    saved = {
        "youtube:PL1": {"name": "Mix", "source": "youtube", "id": "PL1"},
        "spotify:SP1": {"name": "Chill", "source": "spotify", "id": "SP1"},
    }
    youtube, skipped = ps.select_youtube_playlist_sources(
        saved, ["youtube:PL1", "spotify:SP1", "missing:key"]
    )
    assert [p["name"] for p in youtube] == ["Mix"]
    assert youtube[0]["id"] == "PL1"
    assert [p["source"] for p in skipped] == ["spotify"]


def test_combined_track_key_prefers_title_artist_then_id():
    assert ps.combined_track_key({"title": "Song", "artist": "Artist"}) == "song artist"
    # No title/artist -> falls back to source:id.
    assert ps.combined_track_key({"source": "youtube", "videoId": "abc"}) == "youtube:abc"
    assert ps.combined_track_key({"id": "xyz"}) == "youtube:xyz"
    # Nothing usable -> None.
    assert ps.combined_track_key({}) is None
