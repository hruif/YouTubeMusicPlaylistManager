#!/usr/bin/env python3
"""
Test playlist persistence functionality.
"""

import json
import tempfile
from pathlib import Path


def test_playlist_persistence(tmp_path):
    print("Testing playlist persistence...")

    test_playlists = {
        'PL1': {
            'name': 'My Favorites',
            'videos': ['vid1', 'vid2', 'vid3']
        },
        'PL2': {
            'name': 'Chill Music',
            'videos': ['vid2', 'vid4', 'vid5']
        }
    }

    test_file = tmp_path / 'test_playlists.json'

    print("Testing save...")
    with test_file.open('w', encoding='utf-8') as f:
        json.dump(test_playlists, f, indent=2, ensure_ascii=False)
    print("✓ Save successful")

    print("Testing load...")
    with test_file.open('r', encoding='utf-8') as f:
        loaded_data = json.load(f)

    assert loaded_data == test_playlists
    print("✓ Load successful - data integrity verified")

    print("Testing with sets...")
    test_playlists_sets = {
        'PL1': {
            'name': 'My Favorites',
            'videos': {'vid1', 'vid2', 'vid3'}
        }
    }

    json_data = {}
    for pl_id, pl_data in test_playlists_sets.items():
        json_data[pl_id] = {
            'name': pl_data['name'],
            'videos': sorted(pl_data['videos'])
        }

    with test_file.open('w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    with test_file.open('r', encoding='utf-8') as f:
        loaded_json = json.load(f)

    reconstructed = {}
    for pl_id, pl_data in loaded_json.items():
        reconstructed[pl_id] = {
            'name': pl_data['name'],
            'videos': set(pl_data['videos'])
        }

    assert reconstructed == test_playlists_sets
    print("✓ Set conversion successful")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        test_playlist_persistence(Path(temp_dir))
