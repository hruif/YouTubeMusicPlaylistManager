import json
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

from ytmusicapi import YTMusic
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
        temporary_playlists_file=None,
        ytmusic_cls=YTMusic,
        credentials_cls=OAuthCredentials,
        opener=webbrowser.open,
    ):
        self.client_file = Path(client_file or private_user_data_path("ytmusic_oauth_client.json"))
        self.token_file = Path(token_file or private_user_data_path("ytmusic_oauth_token.json"))
        self.temporary_playlists_file = Path(
            temporary_playlists_file or private_user_data_path("temporary_youtube_playlists.json")
        )
        self.ytmusic_cls = ytmusic_cls
        self.credentials_cls = credentials_cls
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
        with self.temporary_playlists_file.open("w", encoding="utf-8") as file:
            json.dump([record.as_dict() for record in records], file, indent=2)

    def remember_temporary_playlist(self, playlist_id, title, source_playlists):
        playlist_id = str(playlist_id or "").strip()
        if not playlist_id:
            raise ValueError("Temporary playlist ID is required.")

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
        records = [
            record
            for record in self.load_temporary_playlists()
            if record.playlist_id not in playlist_ids
        ]
        self.save_temporary_playlists(records)

    def clear_temporary_playlist_records(self):
        self.save_temporary_playlists([])
