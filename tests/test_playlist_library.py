#!/usr/bin/env python3
"""Tests for PlaylistLibrary load/save/delete/migration orchestration."""

import json

from app.services.playlist_library import PlaylistLibrary


def _normalize(stored_key, pl_data):
    if not isinstance(pl_data, dict) or not pl_data.get("id"):
        return None
    return {
        "source": pl_data.get("source", "youtube"),
        "id": pl_data["id"],
        "name": pl_data.get("name", "Unnamed"),
        "videos": set(pl_data.get("videos") or []),
        "tracks": pl_data.get("tracks", []),
    }


def _serialize(key, pl_data):
    return {
        "source": pl_data["source"],
        "id": pl_data["id"],
        "name": pl_data["name"],
        "videos": sorted(pl_data.get("videos") or []),
        "tracks": pl_data.get("tracks", []),
    }


def _sort_key(item):
    _key, data = item
    return data.get("name", "").lower()


def _library(tmp_path):
    return PlaylistLibrary(tmp_path / "saved.json", _normalize, _serialize, _sort_key)


def test_save_then_load_round_trips(tmp_path):
    lib = _library(tmp_path)
    lib.playlists = {
        "youtube:PL1": {"source": "youtube", "id": "PL1", "name": "Mix", "videos": {"a", "b"}, "tracks": []},
    }
    lib.save()

    reloaded = _library(tmp_path)
    migrated = reloaded.load()
    assert migrated is False  # written in current format under the canonical key
    assert set(reloaded.playlists) == {"youtube:PL1"}
    assert reloaded.playlists["youtube:PL1"]["videos"] == {"a", "b"}


def test_load_missing_file_starts_empty(tmp_path):
    lib = _library(tmp_path)
    assert lib.load() is False
    assert lib.playlists == {}


def test_load_flags_migration_for_legacy_key(tmp_path):
    path = tmp_path / "saved.json"
    # Legacy bare key (not "youtube:PL1") -> store key differs -> migration needed.
    path.write_text(json.dumps({"PL1": {"id": "PL1", "source": "youtube", "name": "Old", "videos": ["a"], "tracks": []}}), encoding="utf-8")
    lib = _library(tmp_path)
    assert lib.load() is True
    assert set(lib.playlists) == {"youtube:PL1"}


def test_corrupted_file_is_backed_up_and_starts_empty(tmp_path):
    path = tmp_path / "saved.json"
    path.write_text("{ not valid json", encoding="utf-8")
    lib = _library(tmp_path)
    assert lib.load() is False
    assert lib.playlists == {}
    assert (tmp_path / "saved.json.backup").exists()


def test_delete_removes_and_reports_count(tmp_path):
    lib = _library(tmp_path)
    lib.playlists = {
        "youtube:PL1": {"source": "youtube", "id": "PL1", "name": "A", "videos": set(), "tracks": []},
        "youtube:PL2": {"source": "youtube", "id": "PL2", "name": "B", "videos": set(), "tracks": []},
    }
    assert lib.delete(["youtube:PL1", "missing"]) == 1
    assert set(lib.playlists) == {"youtube:PL2"}


def test_sorted_items_orders_by_name(tmp_path):
    lib = _library(tmp_path)
    lib.playlists = {
        "youtube:PL1": {"source": "youtube", "id": "PL1", "name": "Zebra", "videos": set(), "tracks": []},
        "youtube:PL2": {"source": "youtube", "id": "PL2", "name": "Apple", "videos": set(), "tracks": []},
    }
    assert [data["name"] for _key, data in lib.sorted_items()] == ["Apple", "Zebra"]
