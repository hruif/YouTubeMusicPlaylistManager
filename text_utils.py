"""Pure, Tk-free text and formatting helpers extracted from the UI controller.

Dependency-free (no tkinter, no app state) so they can be unit-tested directly.
"""
import re
import time
from datetime import datetime

_SOURCE_PREFIXES = {"youtube": "YouTube", "spotify": "Spotify"}


def normalize_search_text(text):
    normalized = str(text or "").lower()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def matches_find_query(values, query):
    terms = [term for term in normalize_search_text(query).split() if term]
    if not terms:
        return True

    haystack = normalize_search_text(" ".join(str(value or "") for value in values))
    return all(term in haystack for term in terms)


def format_relative_age(created_at, now=None):
    try:
        created_at = int(created_at)
    except (TypeError, ValueError):
        created_at = 0
    if created_at <= 0:
        return "unknown age"

    if now is None:
        now = int(time.time())
    seconds = max(0, int(now) - created_at)
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    if days >= 1:
        return f"{days} day{'' if days == 1 else 's'} ago"
    if hours >= 1:
        return f"{hours} hour{'' if hours == 1 else 's'} ago"
    if minutes >= 1:
        return f"{minutes} minute{'' if minutes == 1 else 's'} ago"
    return "just now"


def format_timestamp(created_at):
    try:
        created_at = int(created_at)
    except (TypeError, ValueError):
        created_at = 0
    if created_at <= 0:
        return "Unknown"
    return datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")


def fit_text_to_pixels(text, font, max_pixels):
    # Truncate text with an ellipsis so it fits within max_pixels for the given font.
    # `font` is any object exposing a .measure(str) -> int (e.g. a tkinter font).
    text = str(text)
    if max_pixels <= 0 or not text or font.measure(text) <= max_pixels:
        return text
    ellipsis = "…"
    truncated = text
    while truncated and font.measure(truncated + ellipsis) > max_pixels:
        truncated = truncated[:-1]
    return (truncated.rstrip() + ellipsis) if truncated else ellipsis


def temp_playlist_source_names(record):
    # Just the playlist names, no "YouTube:"/"Spotify:" prefix.
    names = []
    for source in getattr(record, "source_playlists", None) or []:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name") or "").strip()
        if name:
            names.append(name)
    return ", ".join(names)


def temp_playlist_source_kinds(record):
    kinds = set()
    for source in getattr(record, "source_playlists", None) or []:
        if not isinstance(source, dict):
            continue
        kind = str(source.get("source") or "").strip().lower()
        if kind:
            kinds.add(kind)
    return kinds


def temp_playlist_sources_text(record):
    names = []
    for source in getattr(record, "source_playlists", None) or []:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name") or "").strip()
        source_kind = str(source.get("source") or "").strip().lower()
        prefix = _SOURCE_PREFIXES.get(source_kind, "")
        if name:
            names.append(f"{prefix}: {name}" if prefix else name)
    return ", ".join(names)
