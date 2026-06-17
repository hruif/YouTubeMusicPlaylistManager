"""Spotify -> YouTube Music track matching for the "Convert to YouTube playlist" transfer.

Conservative by design: only a confident title+artist match is accepted, so the transfer
auto-adds the songs it's sure about and lists the rest for you to handle manually. Pure
logic (unit-tested); the controller runs the actual ytmusicapi search per track.
"""
from app.services.text_utils import normalize_search_text


def artists_text(artists):
    """Join a ytmusicapi search result's `artists` (list of {name}) into a string."""
    if isinstance(artists, str):
        return artists
    if not isinstance(artists, list):
        return ""
    return ", ".join(
        artist.get("name", "")
        for artist in artists
        if isinstance(artist, dict) and artist.get("name")
    )


def is_confident_match(target_title, target_artist, candidate_title, candidate_artist):
    """True only when the candidate is clearly the same song: one title's words are a subset
    of the other's (so "Song" matches "Song (feat. X)"), and at least one artist word
    overlaps (unless the source has no artist)."""
    target_title_tokens = set(normalize_search_text(target_title).split())
    candidate_title_tokens = set(normalize_search_text(candidate_title).split())
    if not target_title_tokens or not candidate_title_tokens:
        return False

    title_ok = (
        target_title_tokens.issubset(candidate_title_tokens)
        or candidate_title_tokens.issubset(target_title_tokens)
    )
    if not title_ok:
        return False

    target_artist_tokens = set(normalize_search_text(target_artist).split())
    candidate_artist_tokens = set(normalize_search_text(candidate_artist).split())
    return (not target_artist_tokens) or bool(target_artist_tokens & candidate_artist_tokens)


def best_youtube_match(search_results, target_title, target_artist):
    """The first confident match in a YouTube Music songs-search result list (results are
    relevance-ranked), or None. Returns {videoId, title, artist}."""
    for candidate in search_results or []:
        if not isinstance(candidate, dict):
            continue
        video_id = candidate.get("videoId")
        if not video_id:
            continue
        candidate_title = candidate.get("title") or ""
        candidate_artist = artists_text(candidate.get("artists"))
        if is_confident_match(target_title, target_artist, candidate_title, candidate_artist):
            return {"videoId": video_id, "title": candidate_title, "artist": candidate_artist}
    return None
