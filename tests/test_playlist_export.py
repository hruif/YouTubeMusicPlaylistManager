#!/usr/bin/env python3
"""Tests for the CSV playlist export formatter."""

from app.services import playlist_export


def test_build_csv_has_header_and_rows():
    tracks = [
        {"title": "Song A", "artist": "Artist A", "source": "youtube", "videoId": "vidA"},
        {"title": "Song B", "artist": "Artist B", "source": "spotify", "trackId": "trkB"},
    ]
    csv_text = playlist_export.build_csv(tracks)
    lines = csv_text.strip().splitlines()
    assert lines[0] == "Title,Artist,Source,ID"
    assert lines[1] == "Song A,Artist A,youtube,vidA"
    assert lines[2] == "Song B,Artist B,spotify,trkB"


def test_build_csv_handles_missing_fields_and_quoting():
    csv_text = playlist_export.build_csv([
        {"title": "Comma, Song", "id": "x"},   # missing artist/source; comma forces quoting
        "not-a-dict",                            # skipped
    ])
    lines = csv_text.strip().splitlines()
    assert lines[0] == "Title,Artist,Source,ID"
    assert lines[1] == '"Comma, Song",,,x'
    assert len(lines) == 2


def test_build_csv_empty():
    assert playlist_export.build_csv([]).strip() == "Title,Artist,Source,ID"
    assert playlist_export.build_csv(None).strip() == "Title,Artist,Source,ID"
