#!/usr/bin/env python3
"""
Tests for bundled UI assets.
"""

import struct
from pathlib import Path


ASSETS_DIR = Path(__file__).with_name("assets")


def test_source_logo_assets_exist_with_expected_sizes():
    expected_sizes = {
        "youtube_18.png": (18, 18),
        "youtube_24.png": (24, 24),
        "spotify_18.png": (18, 18),
        "spotify_24.png": (24, 24),
        "mixed_24.png": (24, 24),
    }

    for filename, expected_size in expected_sizes.items():
        asset_path = ASSETS_DIR / filename
        assert asset_path.exists(), f"Missing asset: {filename}"
        with asset_path.open("rb") as asset_file:
            header = asset_file.read(24)

        assert header.startswith(b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", header[16:24])
        assert (width, height) == expected_size
