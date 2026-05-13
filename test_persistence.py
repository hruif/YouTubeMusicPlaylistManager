#!/usr/bin/env python3
"""
Test playlist persistence functionality
"""

import json
import os

def test_playlist_persistence():
    print("Testing playlist persistence...")

    # Sample playlist data
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

    test_file = 'test_playlists.json'

    try:
        # Test saving
        print("Testing save...")
        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(test_playlists, f, indent=2, ensure_ascii=False)
        print("✓ Save successful")

        # Test loading
        print("Testing load...")
        with open(test_file, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)

        # Verify data integrity
        if loaded_data == test_playlists:
            print("✓ Load successful - data integrity verified")
        else:
            print("✗ Data integrity check failed")
            print(f"Original: {test_playlists}")
            print(f"Loaded: {loaded_data}")

        # Test with video sets (our actual data structure)
        print("Testing with sets...")
        test_playlists_sets = {
            'PL1': {
                'name': 'My Favorites',
                'videos': {'vid1', 'vid2', 'vid3'}  # set
            }
        }

        # Convert sets to lists for JSON (since sets aren't JSON serializable)
        json_data = {}
        for pl_id, pl_data in test_playlists_sets.items():
            json_data[pl_id] = {
                'name': pl_data['name'],
                'videos': list(pl_data['videos'])  # convert set to list
            }

        with open(test_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # Load and convert back to sets
        with open(test_file, 'r', encoding='utf-8') as f:
            loaded_json = json.load(f)

        reconstructed = {}
        for pl_id, pl_data in loaded_json.items():
            reconstructed[pl_id] = {
                'name': pl_data['name'],
                'videos': set(pl_data['videos'])  # convert list back to set
            }

        if reconstructed == test_playlists_sets:
            print("✓ Set conversion successful")
        else:
            print("✗ Set conversion failed")

    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)
            print("✓ Cleanup completed")

if __name__ == "__main__":
    test_playlist_persistence()