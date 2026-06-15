import json
import time
from pathlib import Path

import requests


class YouTubeDataApiError(RuntimeError):
    """Raised when the official YouTube Data API returns an error response."""


class YouTubeDataApiClient:
    """Small wrapper for the official YouTube Data API playlist endpoints."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    PLAYLISTS_URL = "https://www.googleapis.com/youtube/v3/playlists"

    def __init__(self, client_file, token_file, session=None):
        self.client_file = Path(client_file)
        self.token_file = Path(token_file)
        self.session = session or requests.Session()

    def create_playlist(self, title, description, privacy_status="private"):
        response = self._request(
            "POST",
            self.PLAYLISTS_URL,
            params={"part": "snippet,status"},
            json={
                "snippet": {
                    "title": title,
                    "description": description,
                },
                "status": {
                    "privacyStatus": privacy_status.lower(),
                },
            },
            expected_status={200},
        )
        playlist_id = response.get("id")
        if not playlist_id:
            raise YouTubeDataApiError(f"YouTube Data API did not return a playlist id: {response}")
        return playlist_id

    def delete_playlist(self, playlist_id):
        self._request(
            "DELETE",
            self.PLAYLISTS_URL,
            params={"id": playlist_id},
            expected_status={204},
        )

    def _request(self, method, url, params=None, json=None, expected_status=None):
        expected_status = expected_status or {200}
        access_token = self._access_token()
        response = self.session.request(
            method,
            url,
            params=params,
            json=json,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=30,
        )

        if response.status_code == 401:
            access_token = self._refresh_access_token(force=True)
            response = self.session.request(
                method,
                url,
                params=params,
                json=json,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                timeout=30,
            )

        if response.status_code not in expected_status:
            raise YouTubeDataApiError(self._format_error_response(response))

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def _access_token(self):
        token_data = self._load_json(self.token_file)
        if token_data.get("access_token") and int(token_data.get("expires_at") or 0) > time.time() + 60:
            return token_data["access_token"]
        return self._refresh_access_token()

    def _refresh_access_token(self, force=False):
        token_data = self._load_json(self.token_file)
        if (
            not force
            and token_data.get("access_token")
            and int(token_data.get("expires_at") or 0) > time.time() + 60
        ):
            return token_data["access_token"]

        client_data = self._load_json(self.client_file)
        refresh_token = token_data.get("refresh_token")
        if not client_data.get("client_id") or not client_data.get("client_secret") or not refresh_token:
            raise YouTubeDataApiError("Saved YouTube OAuth credentials are incomplete.")

        response = self.session.post(
            self.TOKEN_URL,
            data={
                "client_id": client_data["client_id"],
                "client_secret": client_data["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise YouTubeDataApiError(self._format_error_response(response))

        refreshed = response.json()
        token_data.update(refreshed)
        token_data["refresh_token"] = refresh_token
        token_data["expires_at"] = int(time.time()) + int(refreshed.get("expires_in") or 0)
        self._save_json(self.token_file, token_data)
        return token_data["access_token"]

    def _load_json(self, path):
        try:
            with Path(path).open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_json(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

    def _format_error_response(self, response):
        try:
            payload = response.json()
        except ValueError:
            payload = response.text

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message") or payload
                details = error.get("errors") or []
                reasons = [
                    detail.get("reason")
                    for detail in details
                    if isinstance(detail, dict) and detail.get("reason")
                ]
                if reasons:
                    return f"YouTube Data API HTTP {response.status_code}: {message} ({', '.join(reasons)})"
                return f"YouTube Data API HTTP {response.status_code}: {message}"

        return f"YouTube Data API HTTP {response.status_code}: {payload}"
