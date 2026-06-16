#!/usr/bin/env python3
"""Tests for the single-instance lock."""

from app.app_lock import SingleInstanceLock


def test_single_instance_lock_blocks_second_holder(tmp_path):
    lock_file = tmp_path / "instance.lock"

    first = SingleInstanceLock(lock_file=lock_file)
    second = SingleInstanceLock(lock_file=lock_file)

    assert first.acquire() is True
    assert second.acquire() is False

    first.release()


def test_single_instance_lock_can_be_reacquired_after_release(tmp_path):
    lock_file = tmp_path / "instance.lock"

    first = SingleInstanceLock(lock_file=lock_file)
    assert first.acquire() is True
    first.release()

    second = SingleInstanceLock(lock_file=lock_file)
    assert second.acquire() is True
    second.release()


def test_single_instance_lock_pidfile_fallback_detects_dead_pid(tmp_path):
    lock_file = tmp_path / "instance.lock"
    # Simulate a stale lock from a process that no longer exists. PID 0 is never
    # a live user process, so the fallback should treat it as stale and acquire.
    lock_file.write_text("999999999", encoding="utf-8")

    lock = SingleInstanceLock(lock_file=lock_file)
    assert lock._acquire_pidfile() is True
    lock.release()
