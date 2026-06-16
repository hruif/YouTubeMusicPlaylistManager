#!/usr/bin/env python3
"""
Tests for YouTube Music OAuth and temporary playlist bookkeeping.
"""

import json

from app.services.youtube_music_account import YouTubeMusicAccount


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
    def __init__(self, auth, oauth_credentials=None):
        self.auth = auth
        self.oauth_credentials = oauth_credentials


def fake_browser_setup(filepath=None, headers_raw=None):
    assert "cookie:" in headers_raw.lower()
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(
            {
                "cookie": "SID=fake",
                "x-goog-authuser": "0",
                "user-agent": "test",
            },
            file,
        )
    return "{}"


def make_account(tmp_path):
    return YouTubeMusicAccount(
        client_file=tmp_path / "client.json",
        token_file=tmp_path / "token.json",
        browser_auth_file=tmp_path / "browser.json",
        temporary_playlists_file=tmp_path / "temporary.json",
        ytmusic_cls=FakeYTMusic,
        credentials_cls=FakeCredentials,
        browser_setup_func=fake_browser_setup,
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


def test_youtube_music_account_saves_browser_headers_for_queue(tmp_path):
    account = make_account(tmp_path)

    assert not account.has_browser_auth()

    auth_path = account.store_browser_auth_headers(
        "cookie: SID=fake\nx-goog-authuser: 0\nuser-agent: test"
    )

    assert auth_path == tmp_path / "browser.json"
    assert account.has_browser_auth()
    assert account.load_browser_auth_data()["cookie"] == "SID=fake"

    client = account.build_browser_authenticated_client()
    assert client.auth == str(tmp_path / "browser.json")
    assert client.oauth_credentials is None


def test_strip_rotating_cookies_keeps_stable_cookies(tmp_path):
    account = make_account(tmp_path)

    stripped = account._strip_rotating_cookies(
        {"cookie": "SID=fake; __Secure-1PSIDTS=rot1; SAPISID=keep; __Secure-3PSIDTS=rot3"}
    )
    assert stripped["cookie"] == "SID=fake; SAPISID=keep"

    # No cookie key / empty: returned unchanged, no crash.
    assert account._strip_rotating_cookies({}) == {}
    assert account._strip_rotating_cookies({"cookie": ""}) == {"cookie": ""}


def test_build_browser_client_strips_rotating_cookies_when_requested(tmp_path):
    account = make_account(tmp_path)
    # Write the auth file directly (the fake setup helper would otherwise overwrite the cookie).
    account.browser_auth_file.write_text(
        json.dumps(
            {
                "cookie": "SID=fake; __Secure-1PSIDTS=rot1; SAPISID=keep; __Secure-3PSIDTS=rot3",
                "x-goog-authuser": "0",
                "authorization": "SAPISIDHASH 123_abc",
            }
        ),
        encoding="utf-8",
    )

    # Default path is unchanged: the file path is handed to ytmusicapi as-is.
    default_client = account.build_browser_authenticated_client()
    assert default_client.auth == str(account.browser_auth_file)

    # Experiment: rotating per-session cookies are dropped, stable ones kept, passed as a dict.
    stripped_client = account.build_browser_authenticated_client(strip_rotating_cookies=True)
    assert isinstance(stripped_client.auth, dict)
    cookie = stripped_client.auth["cookie"]
    assert "SID=fake" in cookie
    assert "SAPISID=keep" in cookie
    assert "__Secure-1PSIDTS" not in cookie
    assert "__Secure-3PSIDTS" not in cookie


def test_youtube_music_account_accepts_chrome_copy_as_fetch_headers(tmp_path):
    account = make_account(tmp_path)

    fetch_text = '''
fetch("https://music.youtube.com/youtubei/v1/browse?prettyPrint=false", {
  "headers": {
    "accept": "*/*",
    "authorization": "SAPISIDHASH fake",
    "content-type": "application/json",
    "x-goog-authuser": "0",
    "x-origin": "https://music.youtube.com",
    "cookie": "SID=fake"
  },
  "body": "{}",
  "method": "POST"
});
'''

    account.store_browser_auth_headers(fetch_text)

    assert account.has_browser_auth()


def test_youtube_music_account_accepts_trimmed_browser_header_json(tmp_path):
    account = make_account(tmp_path)

    account.store_browser_auth_headers(
        '''
{
  "Accept": "*/*",
  "Authorization": "SAPISIDHASH fake",
  "Content-Type": "application/json",
  "X-Goog-AuthUser": "0",
  "x-origin": "https://music.youtube.com",
  "Cookie": "SID=fake",
}
'''
    )

    assert account.has_browser_auth()


def test_youtube_music_account_sanitizes_chrome_header_noise(tmp_path):
    account = make_account(tmp_path)

    dirty_headers = {
        "accept": "*/*",
        "authorization": "SAPISIDHASH fake",
        "content-type": "application/json",
        "cookie": "SID=fake",
        "x-goog-authuser": "0",
        "Decoded": "{",
        "music.youtube.com": "",
        "/youtubei/v1/browse?prettyPrint=false": "",
        "priority": "u=1",
    }
    account.browser_auth_file.write_text(json.dumps(dirty_headers), encoding="utf-8")

    assert account.has_browser_auth()

    account.build_browser_authenticated_client()
    saved = json.loads(account.browser_auth_file.read_text(encoding="utf-8"))

    assert "cookie" in saved
    assert "x-goog-authuser" in saved
    assert "decoded" not in saved
    assert "priority" not in saved
    assert "/youtubei/v1/browse?prettyPrint=false" not in saved


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


def test_forget_temporary_playlists_keeps_other_records(tmp_path):
    account = make_account(tmp_path)

    account.remember_temporary_playlist("PL_A", "Queue A", [])
    account.remember_temporary_playlist("PL_B", "Queue B", [])

    account.forget_temporary_playlists(["PL_A"])

    remaining = account.load_temporary_playlists()
    assert [record.playlist_id for record in remaining] == ["PL_B"]


def test_save_temporary_playlists_is_atomic(tmp_path):
    account = make_account(tmp_path)

    account.remember_temporary_playlist("PL_TEMP", "Queue", [])

    # No leftover temp file from the atomic write, and the data is valid JSON.
    tmp_file = account.temporary_playlists_file.with_suffix(
        account.temporary_playlists_file.suffix + ".tmp"
    )
    assert not tmp_file.exists()
    with account.temporary_playlists_file.open(encoding="utf-8") as file:
        assert isinstance(json.load(file), list)


def test_corrupt_temporary_playlists_file_is_ignored(tmp_path):
    account = make_account(tmp_path)
    account.temporary_playlists_file.write_text("not json", encoding="utf-8")

    assert account.load_temporary_playlists() == []

    # A subsequent write recovers the file.
    account.remember_temporary_playlist("PL_TEMP", "Queue", [])
    assert [record.playlist_id for record in account.load_temporary_playlists()] == ["PL_TEMP"]
