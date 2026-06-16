#!/usr/bin/env python3
"""Tests for the persistent application settings store."""

from app.app_settings import AppSettings


def test_app_settings_round_trip(tmp_path):
    settings_file = tmp_path / "app_settings.json"

    settings = AppSettings(settings_file=settings_file)
    assert settings.get("missing", "default") == "default"

    settings.set("auto_delete_temp_on_exit", True)

    reloaded = AppSettings(settings_file=settings_file)
    assert reloaded.get_bool("auto_delete_temp_on_exit") is True


def test_app_settings_get_bool_coerces_truthy_strings(tmp_path):
    settings = AppSettings(settings_file=tmp_path / "settings.json")

    settings.set("flag", "yes")
    assert settings.get_bool("flag") is True

    settings.set("flag", "off")
    assert settings.get_bool("flag") is False

    assert settings.get_bool("never_set", default=True) is True


def test_app_settings_atomic_write_leaves_no_temp_file(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings = AppSettings(settings_file=settings_file)

    settings.set("flag", True)

    assert settings_file.exists()
    assert not settings_file.with_suffix(settings_file.suffix + ".tmp").exists()


def test_app_settings_survives_corrupt_file(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{ not valid json", encoding="utf-8")

    settings = AppSettings(settings_file=settings_file)
    assert settings.get_bool("anything") is False

    settings.set("flag", True)
    assert AppSettings(settings_file=settings_file).get_bool("flag") is True
