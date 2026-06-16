#!/usr/bin/env python3
"""Tests for custom song names (local aliases): key derivation + persistence."""

import json

from app.services import custom_names
from app.services.custom_names import CustomNamesStore


def test_song_key_prefers_title_artist_then_falls_back_to_source_id():
    # Normalized title+artist key (matches combined-view grouping).
    assert custom_names.song_key({"title": "Space Song", "artist": "Beach House"}) == "space song beach house"
    # Fallback to source:id when there's no usable title/artist key.
    assert custom_names.song_key({"videoId": "vid123", "source": "youtube"}) == "youtube:vid123"
    assert custom_names.song_key({"trackId": "t1", "source": "spotify"}) == "spotify:t1"
    # Nothing usable.
    assert custom_names.song_key({}) is None
    assert custom_names.song_key("not-a-dict") is None


def test_store_set_get_and_clear(tmp_path):
    store = CustomNamesStore(store_file=tmp_path / "names.json")
    track = {"title": "君の名は", "artist": "RADWIMPS"}

    assert store.get(track) == ""
    assert store.set(track, "Your Name") is True
    assert store.get(track) == "Your Name"

    # Setting the same value again is a no-op.
    assert store.set(track, "Your Name") is False

    # Empty/whitespace clears it.
    assert store.set(track, "   ") is True
    assert store.get(track) == ""
    # Clearing an absent key is a no-op.
    assert store.set(track, "") is False


def test_store_trims_and_keys_by_song_identity(tmp_path):
    store = CustomNamesStore(store_file=tmp_path / "names.json")
    store.set({"title": "A", "artist": "B"}, "  Alias  ")
    # Same title/artist -> same key, even from a different source/id.
    assert store.get({"title": "a", "artist": "b", "videoId": "x"}) == "Alias"


def test_store_persists_across_instances_and_ignores_bad_rows(tmp_path):
    path = tmp_path / "names.json"
    path.write_text(json.dumps({
        "good key": "Good Name",
        "blank": "   ",        # dropped on load (empty after strip)
        "nonstring": 5,         # dropped on load (not a string)
    }), encoding="utf-8")

    store = CustomNamesStore(store_file=path)
    # "good key" is exactly the normalized key for title "good" / artist "key".
    assert store.get({"title": "good", "artist": "key"}) == "Good Name"
    # Confirm the bad rows were dropped by writing + reloading.
    store.set({"title": "New", "artist": "Song"}, "New Alias")
    reloaded = CustomNamesStore(store_file=path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved.get("good key") == "Good Name"
    assert "blank" not in saved and "nonstring" not in saved
    assert reloaded.get({"title": "New", "artist": "Song"}) == "New Alias"
