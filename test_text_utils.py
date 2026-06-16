#!/usr/bin/env python3
"""Tests for the pure text/formatting helpers in text_utils."""

from types import SimpleNamespace

import text_utils


def test_normalize_search_text_strips_punctuation_and_case():
    assert text_utils.normalize_search_text("  Hello,  WORLD!! ") == "hello world"
    assert text_utils.normalize_search_text(None) == ""


def test_matches_find_query_requires_all_terms():
    assert text_utils.matches_find_query(("Alpha Song", "First Artist"), "alpha first")
    assert not text_utils.matches_find_query(("Alpha Song", "First Artist"), "alpha second")
    assert text_utils.matches_find_query(("Anything",), "")  # empty query matches


def test_format_relative_age_buckets_by_largest_unit():
    now = 1_000_000
    assert text_utils.format_relative_age(now, now=now) == "just now"
    assert text_utils.format_relative_age(now - 5 * 60, now=now) == "5 minutes ago"
    assert text_utils.format_relative_age(now - 2 * 3600, now=now) == "2 hours ago"
    assert text_utils.format_relative_age(now - 3 * 86400, now=now) == "3 days ago"
    assert text_utils.format_relative_age(0, now=now) == "unknown age"


def test_format_timestamp_handles_bad_input():
    assert text_utils.format_timestamp(0) == "Unknown"
    assert text_utils.format_timestamp("not-a-number") == "Unknown"
    assert len(text_utils.format_timestamp(1_000_000)) == len("2001-01-01 00:00")


def test_temp_playlist_sources_text_prefixes_known_sources():
    record = SimpleNamespace(
        source_playlists=[
            {"id": "PL1", "name": "Morning", "source": "youtube"},
            {"id": "SP1", "name": "Evening", "source": "spotify"},
            {"id": "X", "name": "", "source": "youtube"},
        ]
    )
    assert text_utils.temp_playlist_sources_text(record) == "YouTube: Morning, Spotify: Evening"
    assert text_utils.temp_playlist_sources_text(SimpleNamespace(source_playlists=[])) == ""


def test_temp_playlist_source_names_drops_prefix():
    record = SimpleNamespace(
        source_playlists=[
            {"id": "PL1", "name": "Morning", "source": "youtube"},
            {"id": "SP1", "name": "Evening", "source": "spotify"},
            {"id": "X", "name": "", "source": "youtube"},
        ]
    )
    assert text_utils.temp_playlist_source_names(record) == "Morning, Evening"
    assert text_utils.temp_playlist_source_names(SimpleNamespace(source_playlists=[])) == ""


def test_temp_playlist_source_kinds_collects_unique_sources():
    record = SimpleNamespace(
        source_playlists=[
            {"id": "PL1", "name": "Morning", "source": "youtube"},
            {"id": "PL2", "name": "Noon", "source": "youtube"},
            {"id": "SP1", "name": "Evening", "source": "spotify"},
            {"id": "X", "name": "Bad", "source": ""},
        ]
    )
    assert text_utils.temp_playlist_source_kinds(record) == {"youtube", "spotify"}
    assert text_utils.temp_playlist_source_kinds(SimpleNamespace(source_playlists=[])) == set()


def test_fit_text_to_pixels_truncates_with_ellipsis():
    class FakeFont:
        def measure(self, s):
            return len(s) * 10  # 10px per character

    font = FakeFont()

    # Fits: returned unchanged.
    assert text_utils.fit_text_to_pixels("Morning", font, 1000) == "Morning"
    # Too wide: truncated so text + ellipsis fits within the budget.
    fitted = text_utils.fit_text_to_pixels("Morning, Evening", font, 50)
    assert fitted.endswith("…")
    assert font.measure(fitted) <= 50
    # Degenerate budget still returns something printable.
    assert text_utils.fit_text_to_pixels("Morning", font, 0) == "Morning"
