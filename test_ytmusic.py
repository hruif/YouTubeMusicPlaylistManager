#!/usr/bin/env python3

print("Testing YTMusic import...")

try:
    from ytmusicapi import YTMusic
    print("✓ YTMusic imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    exit(1)

print("Testing YTMusic initialization...")

try:
    ytm = YTMusic()
    print("✓ YTMusic initialized without authentication")
except Exception as e:
    print(f"✗ Init error: {e}")

print("Testing search...")
try:
    results = ytm.search("test", filter="songs")
    print(f"✓ Search works, found {len(results)} results")
except Exception as e:
    print(f"✗ Search error: {e}")

print("Done.")