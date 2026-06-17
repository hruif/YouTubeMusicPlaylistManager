#!/usr/bin/env python3
"""Report GitHub Release download counts for the app.

Tier 1 usage tracking (see dev-docs/FUTURE_DIRECTIONS.md): GitHub already counts how many times
each release asset was downloaded. This reads those counts from the public API — no app changes,
no telemetry, no privacy surface. It's for your own reference, not shown on the download page.

Usage:
    python3 tools/download_stats.py
    python3 tools/download_stats.py --repo owner/name

Notes:
- The public API allows 60 requests/hour unauthenticated. Set GITHUB_TOKEN to raise that limit.
- Counts are *downloads*, not people: re-downloads, each version separately, and bots all count,
  and this says nothing about whether the app is actually run (that's Tier 3).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_REPO = "hruif/YouTubeMusicPlaylistManager"


def fetch_releases(repo: str) -> list[dict]:
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    headers = {"User-Agent": "download_stats", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.load(exc).get("message", "")
        except Exception:
            pass
        sys.exit(f"GitHub API error {exc.code}: {detail or exc.reason}")
    except urllib.error.URLError as exc:
        sys.exit(f"Network error: {exc.reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Report GitHub Release download counts.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help=f"owner/name (default: {DEFAULT_REPO})")
    args = parser.parse_args()

    releases = fetch_releases(args.repo)
    if not releases:
        print(f"No releases found for {args.repo}.")
        return

    total = 0
    print(f"Download counts for {args.repo}:\n")
    for release in releases:
        tag = release.get("tag_name") or "(untagged)"
        flags = []
        if release.get("draft"):
            flags.append("draft")
        if release.get("prerelease"):
            flags.append("prerelease")
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        assets = release.get("assets") or []
        if not assets:
            print(f"  {tag}{suffix}: (no attached assets)")
            continue
        release_total = 0
        for asset in assets:
            count = asset.get("download_count", 0)
            release_total += count
            total += count
            print(f"  {tag}{suffix}  {asset.get('name')}: {count}")
        if len(assets) > 1:
            print(f"    └─ {tag} subtotal: {release_total}")

    print(f"\nTOTAL asset downloads: {total}")


if __name__ == "__main__":
    main()
