#!/usr/bin/env python3
"""
Tests for YouTube Music OAuth and temporary playlist bookkeeping.
"""

import json

from youtube_music_account import YouTubeMusicAccount


class FakeCredentials:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    def get_code(self):
        return {
            "device_code": "device-code",
            "user_code": "USER-CODE",
            "verification_url": "https://example.com/device",
            "expires_in": 900,
            "interval": 1,
        }

    def token_from_code(self, device_code):
        assert device_code == "device-code"
        return {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/youtube",
            "token_type": "Bearer",
        }


class FakeYTMusic:
    def __init__(self, auth, oauth_credentials):
        self.auth = auth
        self.oauth_credentials = oauth_credentials


def make_account(tmp_path):
    return YouTubeMusicAccount(
        client_file=tmp_path / "client.json",
        token_file=tmp_path / "token.json",
        temporary_playlists_file=tmp_path / "temporary.json",
        ytmusic_cls=FakeYTMusic,
        credentials_cls=FakeCredentials,
        opener=lambda _url: None,
    )


def test_youtube_music_account_saves_client_and_token(tmp_path):
    account = make_account(tmp_path)

    assert not account.is_ready()

    account.save_client_credentials("client-id", "client-secret")
    assert account.load_client_credentials() == {
        "client_id": "client-id",
        "client_secret": "client-secret",
    }
    assert account.request_device_code()["user_code"] == "USER-CODE"

    token = account.token_from_device_code("device-code")
    token_path = account.store_token(token)

    assert token_path == tmp_path / "token.json"
    token_data = json.loads((tmp_path / "token.json").read_text(encoding="utf-8"))
    assert token_data["access_token"] == "access"
    assert token_data["refresh_token"] == "refresh"
    assert token_data["expires_at"] > 0
    assert account.load_token_data()["access_token"] == "access"
    assert account.is_ready()

    client = account.build_authenticated_client()
    assert client.auth == str(tmp_path / "token.json")
    assert client.oauth_credentials.client_id == "client-id"
    assert client.oauth_credentials.client_secret == "client-secret"


def test_youtube_music_account_rejects_incomplete_tokens(tmp_path):
    account = make_account(tmp_path)
    account.save_client_credentials("client-id", "client-secret")

    (tmp_path / "token.json").write_text(
        json.dumps(
            {
                "access_token": "access",
                "scope": "https://www.googleapis.com/auth/youtube",
                "token_type": "Bearer",
                "expires_at": 123,
            }
        ),
        encoding="utf-8",
    )

    assert account.load_token_data() is None
    assert not account.has_token()
    assert not account.is_ready()


def test_youtube_music_account_requires_refresh_token_when_storing(tmp_path):
    account = make_account(tmp_path)
    account.save_client_credentials("client-id", "client-secret")

    try:
        account.store_token(
            {
                "access_token": "access",
                "expires_in": 3600,
                "scope": "https://www.googleapis.com/auth/youtube",
                "token_type": "Bearer",
            }
        )
    except RuntimeError as error:
        assert "refresh token" in str(error)
        assert "third-party access" in str(error)
    else:
        raise AssertionError("Incomplete token should not be saved")

    assert not (tmp_path / "token.json").exists()


def test_youtube_music_account_ignores_unsupported_google_token_fields(tmp_path):
    account = make_account(tmp_path)
    account.save_client_credentials("client-id", "client-secret")

    account.store_token(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "refresh_token_expires_in": 604800,
            "scope": "https://www.googleapis.com/auth/youtube",
            "token_type": "Bearer",
        }
    )

    token_data = json.loads((tmp_path / "token.json").read_text(encoding="utf-8"))
    assert token_data["refresh_token"] == "refresh"
    assert "refresh_token_expires_in" not in token_data
    assert account.is_ready()


def test_youtube_music_account_tracks_temporary_playlists(tmp_path):
    account = make_account(tmp_path)

    account.remember_temporary_playlist(
        "PL_TEMP",
        "Temporary Queue",
        [{"id": "PL_SOURCE", "name": "Source Playlist", "source": "youtube"}],
    )

    records = account.load_temporary_playlists()
    assert len(records) == 1
    assert records[0].playlist_id == "PL_TEMP"
    assert records[0].source_playlists[0]["name"] == "Source Playlist"
    assert account.playlist_url("PL_TEMP") == "https://music.youtube.com/playlist?list=PL_TEMP"

    account.forget_temporary_playlists(["PL_TEMP"])
    assert account.load_temporary_playlists() == []
