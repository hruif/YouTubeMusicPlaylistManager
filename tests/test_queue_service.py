#!/usr/bin/env python3
"""Tests for QueueService — the non-UI YouTube Music queue orchestration."""

from types import SimpleNamespace

import pytest

from app.services.queue_service import QueueService


class FakeAccount:
    def __init__(self):
        self.remembered = []

    def remember_temporary_playlist(self, playlist_id, title, sources):
        self.remembered.append((playlist_id, title, sources))


class FakeClient:
    def __init__(self, fail_video_ids=None, delete_raises=None):
        self.fail_video_ids = set(fail_video_ids or [])
        self.delete_raises = set(delete_raises or [])
        self.added = []
        self.deleted = []

    def create_playlist(self, title, description, privacy_status="PRIVATE", video_ids=None):
        return "TEMP"

    def add_playlist_items(self, playlist_id, videoIds=None, duplicates=False):
        ids = list(videoIds or [])
        self.added.append(ids)
        if any(v in self.fail_video_ids for v in ids):
            return {"status": "STATUS_FAILED"}
        return {"status": "STATUS_SUCCEEDED"}

    def delete_playlist(self, playlist_id):
        self.deleted.append(playlist_id)
        if playlist_id in self.delete_raises:
            raise RuntimeError("boom")
        return "STATUS_SUCCEEDED"


def _service():
    return QueueService(FakeAccount(), chunk_size=50)


def test_create_temp_playlist_happy_path_remembers_sources():
    account = FakeAccount()
    service = QueueService(account, chunk_size=50)
    client = FakeClient()
    sources = [{"id": "PL1", "name": "Mix", "source": "youtube"}]

    title, temp_id, skipped = service.create_temp_playlist(client, ["a", "b", "c"], sources, lambda _t: None)

    assert temp_id == "TEMP"
    assert skipped == []
    assert account.remembered and account.remembered[0][0] == "TEMP"
    assert account.remembered[0][2] == sources


def test_create_temp_playlist_rejects_empty_video_ids():
    service = _service()
    with pytest.raises(RuntimeError):
        service.create_temp_playlist(FakeClient(), [], [], lambda _t: None)


def test_create_playlist_with_videos_returns_id_and_does_not_remember():
    account = FakeAccount()
    service = QueueService(account, chunk_size=50)
    client = FakeClient(fail_video_ids=["bad"])

    playlist_id, skipped = service.create_playlist_with_videos(
        client, "My Mix", "desc", ["seed", "ok", "bad"], lambda _t: None
    )

    assert playlist_id == "TEMP"
    assert [item["video_id"] for item in skipped] == ["bad"]
    assert account.remembered == []  # permanent create must not touch temp bookkeeping


def test_create_temp_playlist_reports_rejected_songs():
    service = _service()
    # The seed is the first id; "bad" is rejected when added, isolated by adaptive splitting.
    client = FakeClient(fail_video_ids={"bad"})
    _title, _id, skipped = service.create_temp_playlist(client, ["seed", "ok", "bad"], [], lambda _t: None)
    assert [item["video_id"] for item in skipped] == ["bad"]


def test_delete_temp_playlists_splits_success_and_failure():
    service = _service()
    client = FakeClient(delete_raises={"PL2"})
    records = [
        SimpleNamespace(playlist_id="PL1", title="One"),
        SimpleNamespace(playlist_id="PL2", title="Two"),
    ]
    deleted, failed = service.delete_temp_playlists(client, records, lambda _t: None)
    assert deleted == ["PL1"]
    assert [r.playlist_id for r, _e in failed] == ["PL2"]


def test_chunks_and_response_helpers():
    assert list(QueueService._chunks([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert QueueService._response_succeeded("STATUS_SUCCEEDED") is True
    assert QueueService._response_succeeded({"status": "STATUS_FAILED"}) is False
