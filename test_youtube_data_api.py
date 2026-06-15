import json
import time

from youtube_data_api import YouTubeDataApiClient, YouTubeDataApiError


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self.payload = payload or {}
        self.content = json.dumps(self.payload).encode("utf-8") if status_code != 204 else b""
        self.text = json.dumps(self.payload)

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.responses.pop(0)


def write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_youtube_data_api_creates_playlist_with_existing_access_token(tmp_path):
    client_file = tmp_path / "client.json"
    token_file = tmp_path / "token.json"
    write_json(client_file, {"client_id": "client", "client_secret": "secret"})
    write_json(
        token_file,
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": int(time.time()) + 3600,
            "scope": "https://www.googleapis.com/auth/youtube",
            "token_type": "Bearer",
        },
    )
    session = FakeSession([FakeResponse(200, {"id": "PL_TEMP"})])

    api = YouTubeDataApiClient(client_file, token_file, session=session)

    assert api.create_playlist("Queue", "Description") == "PL_TEMP"
    method, url, kwargs = session.requests[0]
    assert method == "POST"
    assert url == YouTubeDataApiClient.PLAYLISTS_URL
    assert kwargs["params"] == {"part": "snippet,status"}
    assert kwargs["headers"]["Authorization"] == "Bearer access"
    assert kwargs["json"]["status"]["privacyStatus"] == "private"


def test_youtube_data_api_refreshes_expired_access_token(tmp_path):
    client_file = tmp_path / "client.json"
    token_file = tmp_path / "token.json"
    write_json(client_file, {"client_id": "client", "client_secret": "secret"})
    write_json(
        token_file,
        {
            "access_token": "old",
            "refresh_token": "refresh",
            "expires_at": 1,
            "scope": "https://www.googleapis.com/auth/youtube",
            "token_type": "Bearer",
        },
    )
    session = FakeSession([
        FakeResponse(200, {"access_token": "new", "expires_in": 3600, "token_type": "Bearer"}),
        FakeResponse(200, {"id": "PL_TEMP"}),
    ])

    api = YouTubeDataApiClient(client_file, token_file, session=session)

    assert api.create_playlist("Queue", "Description") == "PL_TEMP"
    assert session.requests[0][0] == "POST"
    assert session.requests[0][1] == YouTubeDataApiClient.TOKEN_URL
    assert session.requests[1][2]["headers"]["Authorization"] == "Bearer new"
    token_data = json.loads(token_file.read_text(encoding="utf-8"))
    assert token_data["access_token"] == "new"
    assert token_data["refresh_token"] == "refresh"
    assert token_data["expires_at"] > int(time.time())


def test_youtube_data_api_error_includes_google_reason(tmp_path):
    client_file = tmp_path / "client.json"
    token_file = tmp_path / "token.json"
    write_json(client_file, {"client_id": "client", "client_secret": "secret"})
    write_json(
        token_file,
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": int(time.time()) + 3600,
            "scope": "https://www.googleapis.com/auth/youtube",
            "token_type": "Bearer",
        },
    )
    session = FakeSession([
        FakeResponse(
            403,
            {
                "error": {
                    "message": "Quota exceeded",
                    "errors": [{"reason": "quotaExceeded"}],
                }
            },
        )
    ])

    api = YouTubeDataApiClient(client_file, token_file, session=session)

    try:
        api.create_playlist("Queue", "Description")
    except YouTubeDataApiError as error:
        assert "Quota exceeded" in str(error)
        assert "quotaExceeded" in str(error)
    else:
        raise AssertionError("Expected YouTubeDataApiError")
