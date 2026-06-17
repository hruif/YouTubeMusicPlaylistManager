#!/usr/bin/env python3
"""Tests for the conservative Spotify -> YouTube track matcher."""

from app.services import spotify_matcher


def test_artists_text_joins_names_and_passes_strings():
    assert spotify_matcher.artists_text([{"name": "LiSA"}, {"name": "Aimer"}]) == "LiSA, Aimer"
    assert spotify_matcher.artists_text("Already A String") == "Already A String"
    assert spotify_matcher.artists_text(None) == ""
    assert spotify_matcher.artists_text([{"id": "x"}]) == ""  # no name -> dropped


def test_is_confident_match_accepts_same_song_with_extra_words():
    # Candidate has extra "(feat. ...)" words; still a match.
    assert spotify_matcher.is_confident_match("Unlasting", "LiSA", "Unlasting (feat. Someone)", "LiSA")
    # Punctuation/case differences normalize away.
    assert spotify_matcher.is_confident_match("Your Name.", "RADWIMPS", "your name", "Radwimps")


def test_is_confident_match_rejects_wrong_title_or_artist():
    assert not spotify_matcher.is_confident_match("Unlasting", "LiSA", "Gurenge", "LiSA")     # wrong title
    assert not spotify_matcher.is_confident_match("Unlasting", "LiSA", "Unlasting", "Someone Else")  # wrong artist
    assert not spotify_matcher.is_confident_match("", "LiSA", "Unlasting", "LiSA")            # no target title


def test_best_youtube_match_picks_first_confident_skipping_bad_candidates():
    results = [
        {"title": "Unlasting (Live)", "artists": [{"name": "Cover Band"}]},  # artist mismatch
        {"title": "Unrelated", "artists": [{"name": "LiSA"}], "videoId": "v0"},  # title mismatch
        {"title": "Unlasting", "artists": [{"name": "LiSA"}]},  # confident but NO videoId -> skipped
        {"title": "Unlasting", "artists": [{"name": "LiSA"}], "videoId": "vGOOD"},  # the match
        {"title": "Unlasting", "artists": [{"name": "LiSA"}], "videoId": "vLATER"},
    ]
    match = spotify_matcher.best_youtube_match(results, "Unlasting", "LiSA")
    assert match == {"videoId": "vGOOD", "title": "Unlasting", "artist": "LiSA"}


def test_best_youtube_match_returns_none_when_nothing_confident():
    results = [{"title": "Totally Different", "artists": [{"name": "Nope"}], "videoId": "v1"}]
    assert spotify_matcher.best_youtube_match(results, "Unlasting", "LiSA") is None
    assert spotify_matcher.best_youtube_match([], "Unlasting", "LiSA") is None
