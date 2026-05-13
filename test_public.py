#!/usr/bin/env python3
"""
Test script for public playlist functionality
"""

def test_ytmusic():
    print("Testing YTMusic initialization...")
    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()
        print("✓ YTMusic initialized successfully")

        # Test a simple search
        print("Testing search...")
        results = ytm.search("test", filter="songs", limit=1)
        if results:
            print(f"✓ Search works - found {len(results)} result(s)")
        else:
            print("⚠ Search returned no results")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_playlist_parsing():
    print("Testing playlist URL parsing...")
    test_urls = [
        "https://music.youtube.com/playlist?list=PLrAXtmRdnEQy5KQZF5q9F8mGQ8Xh8Xh8X",
        "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy5KQZF5q9F8mGQ8Xh8Xh8X",
        "PLrAXtmRdnEQy5KQZF5q9F8mGQ8Xh8Xh8X"
    ]

    import re
    for url in test_urls:
        patterns = [
            r'list=([a-zA-Z0-9_-]+)',
            r'playlist/([a-zA-Z0-9_-]+)',
        ]

        found = False
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                print(f"✓ Parsed '{url}' -> '{match.group(1)}'")
                found = True
                break

        if not found and len(url) > 20 and not '/' in url:
            print(f"✓ Direct ID: '{url}'")
        elif not found:
            print(f"✗ Failed to parse: '{url}'")

if __name__ == "__main__":
    print("=== YouTube Music Public Playlist Manager Test ===\n")

    success = test_ytmusic()
    print()
    test_playlist_parsing()

    print("\n=== Test Complete ===")
    if success:
        print("✓ Ready to run: python main.py")
    else:
        print("✗ Issues detected - check ytmusicapi installation")