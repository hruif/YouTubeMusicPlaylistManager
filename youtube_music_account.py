import json
import os
import re
import time
import webbrowser
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ytmusicapi import YTMusic, setup as setup_browser_auth
from ytmusicapi.auth.oauth import OAuthCredentials
from ytmusicapi.auth.oauth.token import RefreshingToken

from app_paths import private_user_data_path


@dataclass
class TemporaryPlaylistRecord:
    playlist_id: str
    title: str
    created_at: int
    source_playlists: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        return cls(
            playlist_id=str(data.get("playlist_id") or data.get("id") or ""),
            title=str(data.get("title") or "Temporary Playlist"),
            created_at=int(data.get("created_at") or 0),
            source_playlists=[
                item
                for item in data.get("source_playlists", [])
                if isinstance(item, dict)
            ]
        )

    def as_dict(self):
        return {
            "playlist_id": self.playlist_id,
            "title": self.title,
            "created_at": self.created_at,
            "source_playlists": self.source_playlists,
        }


class YouTubeMusicAccount:
    """Owns YouTube Music OAuth files and temporary playlist bookkeeping."""

    BROWSER_AUTH_HEADER_ALLOWLIST = {
        "accept",
        "accept-language",
        "authorization",
        "content-type",
        "cookie",
        "origin",
        "user-agent",
        "x-client-data",
        "x-goog-authuser",
        "x-goog-visitor-id",
        "x-origin",
        "x-youtube-bootstrap-logged-in",
        "x-youtube-client-name",
        "x-youtube-client-version",
    }
    REQUIRED_TOKEN_FIELDS = (
        "access_token",
        "refresh_token",
        "scope",
        "token_type",
        "expires_at",
    )
    STORED_TOKEN_FIELDS = REQUIRED_TOKEN_FIELDS + ("expires_in",)

    def __init__(
        self,
        client_file=None,
        token_file=None,
        browser_auth_file=None,
        temporary_playlists_file=None,
        ytmusic_cls=YTMusic,
        credentials_cls=OAuthCredentials,
        browser_setup_func=setup_browser_auth,
        opener=webbrowser.open,
    ):
        self.client_file = Path(client_file or private_user_data_path("ytmusic_oauth_client.json"))
        self.token_file = Path(token_file or private_user_data_path("ytmusic_oauth_token.json"))
        self.browser_auth_file = Path(browser_auth_file or private_user_data_path("ytmusic_browser_auth.json"))
        self.temporary_playlists_file = Path(
            temporary_playlists_file or private_user_data_path("temporary_youtube_playlists.json")
        )
        self.ytmusic_cls = ytmusic_cls
        self.credentials_cls = credentials_cls
        self.browser_setup_func = browser_setup_func
        self.opener = opener

    def load_client_credentials(self):
        try:
            with self.client_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None

        client_id = str(data.get("client_id") or "").strip()
        client_secret = str(data.get("client_secret") or "").strip()
        if not client_id or not client_secret:
            return None

        return {
            "client_id": client_id,
            "client_secret": client_secret,
        }

    def save_client_credentials(self, client_id, client_secret):
        client_id = str(client_id or "").strip()
        client_secret = str(client_secret or "").strip()
        if not client_id or not client_secret:
            raise ValueError("Both OAuth client ID and client secret are required.")

        self.client_file.parent.mkdir(parents=True, exist_ok=True)
        with self.client_file.open("w", encoding="utf-8") as file:
            json.dump(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                file,
                indent=2,
            )

    def has_client_credentials(self):
        return self.load_client_credentials() is not None

    def load_token_data(self):
        try:
            with self.token_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        for field_name in self.REQUIRED_TOKEN_FIELDS:
            if data.get(field_name) in (None, ""):
                return None

        return data

    def has_token(self):
        return self.load_token_data() is not None

    def is_ready(self):
        return self.has_client_credentials() and self.has_token()

    def load_browser_auth_data(self):
        try:
            with self.browser_auth_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        data = self._sanitize_browser_auth_data(data)
        normalized_keys = {str(key).lower() for key in data}
        if not {"cookie", "x-goog-authuser"}.issubset(normalized_keys):
            return None
        return data

    def has_browser_auth(self):
        return self.load_browser_auth_data() is not None

    def store_browser_auth_headers(self, headers_raw):
        headers_raw = str(headers_raw or "").strip()
        if not headers_raw:
            raise ValueError("Paste request headers copied from a logged-in music.youtube.com request.")

        headers_raw = self._normalize_browser_auth_input(headers_raw)
        self.browser_auth_file.parent.mkdir(parents=True, exist_ok=True)
        self.browser_setup_func(filepath=str(self.browser_auth_file), headers_raw=headers_raw)
        self.repair_browser_auth_file()
        if not self.has_browser_auth():
            raise RuntimeError(f"The YouTube Music browser headers could not be saved at {self.browser_auth_file}.")
        return self.browser_auth_file

    def repair_browser_auth_file(self):
        try:
            with self.browser_auth_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        sanitized = self._sanitize_browser_auth_data(data)
        if sanitized != data:
            with self.browser_auth_file.open("w", encoding="utf-8") as file:
                json.dump(sanitized, file, ensure_ascii=True, indent=4, sort_keys=True)
        return sanitized

    def _sanitize_browser_auth_data(self, data):
        sanitized = {}
        for key, value in (data or {}).items():
            normalized_key = str(key).lower().strip()
            if normalized_key not in self.BROWSER_AUTH_HEADER_ALLOWLIST:
                continue
            if value in (None, ""):
                continue
            sanitized[normalized_key] = str(value)
        return sanitized

    def _normalize_browser_auth_input(self, headers_raw):
        headers = self._extract_headers_from_json_or_fetch(headers_raw)
        if not headers:
            return headers_raw

        return "\n".join(
            f"{key}: {value}"
            for key, value in headers.items()
            if value not in (None, "")
        )

    def _extract_headers_from_json_or_fetch(self, text):
        object_text = self._extract_headers_object_text(text)
        if object_text is None and text.lstrip().startswith("{"):
            object_text = text.strip()
        if object_text is None:
            return None

        try:
            headers = json.loads(self._remove_json_trailing_commas(object_text))
        except json.JSONDecodeError:
            return None

        if not isinstance(headers, dict):
            return None
        return {str(key): str(value) for key, value in headers.items()}

    def _extract_headers_object_text(self, text):
        match = re.search(r'["\']?headers["\']?\s*:\s*\{', text)
        if not match:
            return None

        opening_brace = text.find("{", match.start())
        if opening_brace < 0:
            return None

        depth = 0
        quote = None
        escaped = False
        for index in range(opening_brace, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if quote:
                if char == quote:
                    quote = None
                continue
            if char in {"'", '"'}:
                quote = char
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[opening_brace:index + 1]
        return None

    def _remove_json_trailing_commas(self, text):
        return re.sub(r",(\s*[}\]])", r"\1", text)

    def build_browser_authenticated_client(self):
        if not self.repair_browser_auth_file() or not self.has_browser_auth():
            raise RuntimeError("YouTube Music browser headers have not been saved yet.")

        return self.ytmusic_cls(auth=str(self.browser_auth_file))

    def build_oauth_credentials(self):
        credentials = self.load_client_credentials()
        if not credentials:
            raise RuntimeError("YouTube Music OAuth client details have not been saved.")

        return self.credentials_cls(
            credentials["client_id"],
            credentials["client_secret"],
        )

    def build_authenticated_client(self):
        if not self.has_token():
            raise RuntimeError("YouTube Music has not been connected yet, or the saved token is incomplete.")

        return self.ytmusic_cls(
            auth=str(self.token_file),
            oauth_credentials=self.build_oauth_credentials(),
        )

    def request_device_code(self):
        return self.build_oauth_credentials().get_code()

    def token_from_device_code(self, device_code):
        return self.build_oauth_credentials().token_from_code(device_code)

    def store_token(self, token_data):
        token_data = dict(token_data or {})
        if "expires_at" not in token_data:
            token_data["expires_at"] = int(time.time()) + int(token_data.get("expires_in") or 0)

        missing_fields = [
            field_name
            for field_name in self.REQUIRED_TOKEN_FIELDS
            if token_data.get(field_name) in (None, "")
        ]
        if missing_fields:
            if "refresh_token" in missing_fields:
                raise RuntimeError(
                    "Google did not return a refresh token. This can happen if this Google account already "
                    "approved the OAuth client but the local token file was not saved. Remove this app from "
                    "your Google Account third-party access, then start sign-in again with the TVs and "
                    "Limited Input OAuth client."
                )
            raise RuntimeError(
                "Google did not return a complete OAuth token. Missing: "
                f"{', '.join(missing_fields)}. Start sign-in again with the TVs and Limited Input OAuth client."
            )

        stored_token_data = {
            field_name: token_data[field_name]
            for field_name in self.STORED_TOKEN_FIELDS
            if field_name in token_data
        }

        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        token = RefreshingToken(credentials=self.build_oauth_credentials(), **stored_token_data)
        token.store_token(str(self.token_file))
        if not self.has_token():
            raise RuntimeError(f"The YouTube Music token could not be saved at {self.token_file}.")
        return self.token_file

    def disconnect(self, forget_client=False):
        for path in [self.token_file, self.client_file if forget_client else None]:
            if path and path.exists():
                path.unlink()

    def disconnect_browser_auth(self):
        if self.browser_auth_file.exists():
            self.browser_auth_file.unlink()

    def playlist_url(self, playlist_id):
        return f"https://music.youtube.com/playlist?list={playlist_id}"

    def open_playlist(self, playlist_id):
        self.opener(self.playlist_url(playlist_id))

    def load_temporary_playlists(self):
        try:
            with self.temporary_playlists_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(data, list):
            return []

        records = [TemporaryPlaylistRecord.from_dict(item) for item in data if isinstance(item, dict)]
        return [record for record in records if record.playlist_id]

    def save_temporary_playlists(self, records):
        self.temporary_playlists_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.temporary_playlists_file.with_suffix(
            self.temporary_playlists_file.suffix + ".tmp"
        )
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump([record.as_dict() for record in records], file, indent=2)
        os.replace(tmp_path, self.temporary_playlists_file)

    @contextmanager
    def _temporary_playlists_lock(self):
        """Serialize read-modify-write of the records file across processes so a
        second instance cannot clobber records while one is being added/removed."""
        self.temporary_playlists_file.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.temporary_playlists_file.with_suffix(
            self.temporary_playlists_file.suffix + ".lock"
        )
        handle = lock_path.open("w")
        try:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass
            yield
        finally:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            handle.close()

    def remember_temporary_playlist(self, playlist_id, title, source_playlists):
        playlist_id = str(playlist_id or "").strip()
        if not playlist_id:
            raise ValueError("Temporary playlist ID is required.")

        with self._temporary_playlists_lock():
            records = [
                record
                for record in self.load_temporary_playlists()
                if record.playlist_id != playlist_id
            ]
            record = TemporaryPlaylistRecord(
                playlist_id=playlist_id,
                title=title or "Temporary Playlist",
                created_at=int(time.time()),
                source_playlists=source_playlists or [],
            )
            records.insert(0, record)
            self.save_temporary_playlists(records)
        return record

    def forget_temporary_playlists(self, playlist_ids):
        playlist_ids = {str(playlist_id) for playlist_id in playlist_ids}
        with self._temporary_playlists_lock():
            records = [
                record
                for record in self.load_temporary_playlists()
                if record.playlist_id not in playlist_ids
            ]
            self.save_temporary_playlists(records)

    def clear_temporary_playlist_records(self):
        with self._temporary_playlists_lock():
            self.save_temporary_playlists([])
