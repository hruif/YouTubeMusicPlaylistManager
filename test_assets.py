#!/usr/bin/env python3
"""
Tests for bundled UI assets.
"""

import struct
from pathlib import Path


ASSETS_DIR = Path(__file__).with_name("assets")
WEB_DIR = Path(__file__).with_name("web")


def test_source_logo_assets_exist_with_expected_sizes():
    expected_sizes = {
        "youtube_18.png": (18, 18),
        "youtube_24.png": (24, 24),
        "spotify_18.png": (18, 18),
        "spotify_24.png": (24, 24),
        "mixed_24.png": (24, 24),
        "app_icon.png": (512, 512),
    }

    for filename, expected_size in expected_sizes.items():
        asset_path = ASSETS_DIR / filename
        assert asset_path.exists(), f"Missing asset: {filename}"
        with asset_path.open("rb") as asset_file:
            header = asset_file.read(24)

        assert header.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", header[16:24])
        assert (width, height) == expected_size


def test_youtube_queue_player_asset_exists():
    player_path = WEB_DIR / "youtube_queue_player.html"
    launcher_path = Path(__file__).with_name("youtube_player_window.py")

    assert player_path.exists()
    assert launcher_path.exists()
    player_html = player_path.read_text(encoding="utf-8")
    assert "https://www.youtube.com/iframe_api" in player_html
    assert "/queue/" in player_html
    assert "thumbnail-button" in player_html
    assert "player-stage" in player_html
    assert ".thumbnail-button:hover::after" in player_html
    assert "opacity: 0;" in player_html
    assert "removeUnavailableCurrent" in player_html
    assert "reportUnavailableTrack" in player_html
    assert "/unavailable" in player_html
    assert "random-button" in player_html
    assert "randomMode" in player_html
    assert "playbackStatus !== \"YTM only\"" in player_html
    assert "menu-popover" in player_html
    assert "draggable" in player_html
    assert "moveIndex" in player_html


def test_macos_app_icon_asset_exists():
    icon_path = ASSETS_DIR / "app_icon.icns"

    assert icon_path.exists()
    assert icon_path.read_bytes()[:4] == b"icns"
