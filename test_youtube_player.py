#!/usr/bin/env python3
"""
Tests for the local YouTube queue player launcher.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

from app_info import PLAYER_WINDOW_ARG
from youtube_player import YouTubeQueuePlayer
from youtube_player_window import player_window_title


PLAYER_FILE = Path(__file__).with_name("web") / "youtube_queue_player.html"
LAUNCHER_FILE = Path(__file__).with_name("youtube_player_window.py")


def test_store_youtube_queue_limits_cached_queues():
    player = YouTubeQueuePlayer(PLAYER_FILE, queue_cache_limit=2)

    first = player.store_queue('First', [{'videoId': 'one'}])
    second = player.store_queue('Second', [{'videoId': 'two'}])
    third = player.store_queue('Third', [{'videoId': 'three'}])

    assert first not in player.queues
    assert second in player.queues
    assert player.queues[third] == {
        'title': 'Third',
        'tracks': [{'videoId': 'three'}]
    }


def test_youtube_player_server_serves_player_queue_and_unavailable_reports():
    unavailable_reports = []
    player = YouTubeQueuePlayer(PLAYER_FILE, unavailable_callback=unavailable_reports.append)
    player.queues['token'] = {
        'title': 'Local Queue',
        'tracks': [{'videoId': 'yt1', 'title': 'Song'}]
    }
    base_url = player._ensure_server()

    try:
        with urllib.request.urlopen(f'{base_url}/player', timeout=5) as response:
            player_html = response.read().decode('utf-8')
        with urllib.request.urlopen(f'{base_url}/queue/token', timeout=5) as response:
            queue_payload = json.loads(response.read().decode('utf-8'))
        request = urllib.request.Request(
            f'{base_url}/unavailable',
            data=json.dumps({'videoId': 'yt1', 'errorCode': 150}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            unavailable_response = json.loads(response.read().decode('utf-8'))
    finally:
        player.shutdown()

    assert 'YouTube Queue Player' in player_html
    assert queue_payload == {
        'title': 'Local Queue',
        'tracks': [{'videoId': 'yt1', 'title': 'Song'}]
    }
    assert unavailable_response == {}
    assert unavailable_reports == [{'videoId': 'yt1', 'errorCode': 150}]


def test_open_queue_uses_native_launcher_when_available():
    launched = []
    browser_urls = []

    player = YouTubeQueuePlayer(
        PLAYER_FILE,
        launcher_file=LAUNCHER_FILE,
        browser_open=browser_urls.append,
        process_launcher=lambda args, **kwargs: launched.append((args, kwargs)),
        native_available=True
    )

    try:
        open_mode = player.open_queue('Native Queue', [{'videoId': 'yt1'}])
    finally:
        player.shutdown()

    assert open_mode == 'native'
    assert browser_urls == []
    assert launched
    assert launched[0][0][1] == str(LAUNCHER_FILE)
    assert launched[0][0][-1] == 'Native Queue'


def test_open_queue_uses_packaged_player_mode_when_frozen(monkeypatch):
    launched = []
    player = YouTubeQueuePlayer(
        PLAYER_FILE,
        launcher_file=LAUNCHER_FILE,
        process_launcher=lambda args, **kwargs: launched.append((args, kwargs)),
        native_available=True
    )
    monkeypatch.setattr('youtube_player.running_from_bundle', lambda: True)

    try:
        open_mode = player.open_queue('Frozen Queue', [{'videoId': 'yt1'}])
    finally:
        player.shutdown()

    assert open_mode == 'native'
    assert launched[0][0][1] == PLAYER_WINDOW_ARG
    assert launched[0][0][-1] == 'Frozen Queue'


def test_player_window_title_is_app_scoped():
    assert player_window_title("Combined Songs") == "YouTube Music Playlist Manager - Combined Songs"
    assert player_window_title("YouTube Music Playlist Manager - Queue") == "YouTube Music Playlist Manager - Queue"


def test_open_queue_falls_back_to_browser_without_native_launcher():
    browser_urls = []
    player = YouTubeQueuePlayer(
        PLAYER_FILE,
        launcher_file=LAUNCHER_FILE,
        browser_open=browser_urls.append,
        process_launcher=lambda *_args, **_kwargs: None,
        native_available=False
    )

    try:
        open_mode = player.open_queue('Browser Queue', [{'videoId': 'yt1'}])
        parsed_url = urllib.parse.urlparse(browser_urls[0])
    finally:
        player.shutdown()

    assert open_mode == 'browser'
    assert parsed_url.hostname == '127.0.0.1'
    assert parsed_url.path == '/player'
