#!/usr/bin/env python3
"""Tests for user-data path selection, incl. debug-bundle isolation."""

from app import app_paths
from app.app_info import APP_NAME


def test_debug_bundle_uses_separate_data_dir_name(monkeypatch):
    monkeypatch.setattr(app_paths, "running_from_bundle", lambda: True)

    monkeypatch.setenv("PLAYLIST_MANAGER_DEBUG_BUILD", "1")
    assert app_paths._data_dir_app_name() == f"{APP_NAME} (Debug)"

    monkeypatch.delenv("PLAYLIST_MANAGER_DEBUG_BUILD", raising=False)
    assert app_paths._data_dir_app_name() == APP_NAME


def test_from_source_never_uses_debug_data_dir(monkeypatch):
    # Running from source must stay on the normal data dir even with the marker set,
    # so a dev's existing headers/playlists are still found.
    monkeypatch.setattr(app_paths, "running_from_bundle", lambda: False)
    monkeypatch.setenv("PLAYLIST_MANAGER_DEBUG_BUILD", "1")
    assert app_paths._data_dir_app_name() == APP_NAME
