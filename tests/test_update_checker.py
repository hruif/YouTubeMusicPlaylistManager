#!/usr/bin/env python3
"""
Tests for release update detection.
"""

import json

from app.services.update_checker import UpdateChecker, is_newer_version


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_is_newer_version_handles_v_prefix_and_missing_parts():
    assert is_newer_version("v1.2.1", "1.2.0")
    assert is_newer_version("1.3", "1.2.9")
    assert not is_newer_version("1.2.0", "1.2")
    assert not is_newer_version("v1.1.9", "1.2.0")


def test_update_checker_returns_newer_release():
    def opener(request, timeout):
        assert request.full_url == "https://example.com/latest"
        assert timeout == 5
        return FakeResponse({
            "tag_name": "v0.3.0",
            "name": "Release v0.3.0",
            "html_url": "https://example.com/releases/v0.3.0",
            "body": "Changes"
        })

    checker = UpdateChecker(
        current_version="0.2.0",
        release_api_url="https://example.com/latest",
        opener=opener
    )

    update = checker.check()

    assert update.version == "v0.3.0"
    assert update.title == "Release v0.3.0"
    assert update.url == "https://example.com/releases/v0.3.0"
    assert update.notes == "Changes"


def test_update_checker_ignores_current_release():
    checker = UpdateChecker(
        current_version="0.2.0",
        release_api_url="https://example.com/latest",
        opener=lambda *_args, **_kwargs: FakeResponse({"tag_name": "v0.2.0"})
    )

    assert checker.check() is None
