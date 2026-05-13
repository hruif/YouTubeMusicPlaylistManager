#!/usr/bin/env python3
"""
Setup script for YouTube Music authentication.
Run this to create the headers_auth.json file needed for the app.
"""

import sys
import os

def main():
    try:
        from ytmusicapi import setup
        print("Setting up YouTube Music authentication...")
        print("A browser window will open. Please log in to YouTube Music.")
        setup(filepath='headers_auth.json')
        print("✓ Authentication setup complete!")
        print("You can now run: python main.py")
    except ImportError:
        print("✗ ytmusicapi not installed. Run: pip install ytmusicapi")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()