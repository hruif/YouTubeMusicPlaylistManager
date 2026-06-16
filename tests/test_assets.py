#!/usr/bin/env python3
"""
Tests for bundled UI assets.
"""

import struct
from pathlib import Path


# Tests live in tests/, so assets/ is one level up at the repo root.
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


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


def test_macos_app_icon_asset_exists():
    icon_path = ASSETS_DIR / "app_icon.icns"

    assert icon_path.exists()
    assert icon_path.read_bytes()[:4] == b"icns"
