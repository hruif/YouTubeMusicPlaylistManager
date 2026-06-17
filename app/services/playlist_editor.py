"""PlaylistEditor: non-UI add/remove of songs on the user's real YouTube Music
playlists (browser-auth, account-touching — gated behind the queue-actions flag).

Like `QueueService`, the network methods take a ytmusicapi `client` and a
`set_status` is not needed (single-item ops). The pure helpers — target selection,
`setVideoId` extraction, and local-state sync — are unit-tested; the controller owns
the Tk progress window, threading, and auth-expiry prompts.

Removing an item from a YouTube playlist needs its per-playlist `setVideoId`, which
this app does not cache, so `remove_song` fetches the playlist fresh to find it.
"""


class PlaylistEditor:
    def add_song(self, client, playlist_id, video_id):
        """Add one song to a playlist. Raises on failure. Caller pre-checks the song
        isn't already there, so duplicates stay off."""
        response = client.add_playlist_items(playlist_id, videoIds=[video_id], duplicates=False)
        if not _response_succeeded(response):
            raise RuntimeError(_describe_failure("add the song", response))
        return response

    def remove_song(self, client, playlist_id, video_id):
        """Remove every occurrence of `video_id` from a playlist. Raises on failure."""
        playlist = client.get_playlist(playlist_id, limit=None)
        _require_editable(playlist, client)
        set_video_ids = find_set_video_ids(playlist, video_id)
        if not set_video_ids:
            raise RuntimeError(
                "That song was not found in the playlist on YouTube Music "
                "(it may have already been removed there)."
            )
        videos = [{"videoId": video_id, "setVideoId": set_video_id} for set_video_id in set_video_ids]
        response = client.remove_playlist_items(playlist_id, videos)
        if not _response_succeeded(response):
            raise RuntimeError(_describe_failure("remove the song", response))
        return response

    def remove_repeats(self, client, playlist_id):
        """Remove the extra copies of any song listed more than once in this playlist,
        keeping the first occurrence. Returns the number removed (0 if none). Raises on
        failure."""
        playlist = client.get_playlist(playlist_id, limit=None)
        _require_editable(playlist, client)
        extras = find_repeat_items(playlist)
        if not extras:
            return 0
        response = client.remove_playlist_items(playlist_id, extras)
        if not _response_succeeded(response):
            raise RuntimeError(_describe_failure("remove the repeated songs", response))
        return len(extras)


def session_is_authenticated(client):
    """True if the saved session is signed in to an account. A stale/expired snapshot can
    still read public data (requests don't 401) but reports no account and an empty
    library — and then even your own playlists look unowned (no setVideoId), so edits
    silently fail. Used to tell "session expired" apart from "not your playlist"."""
    try:
        info = client.get_account_info()
    except Exception:
        return False
    return bool(isinstance(info, dict) and info.get("accountName"))


def _require_editable(playlist, client):
    """Raise a clear, actionable error when a playlist can't be edited. `owned=False`
    means either the saved session went stale (most common — re-copy headers; this message
    routes to the refresh prompt) or it's genuinely someone else's playlist."""
    if (playlist or {}).get("owned") is not False:
        return
    if not session_is_authenticated(client):
        raise RuntimeError(
            "Your saved YouTube Music headers are no longer signed in to your account "
            "(the session expired). Re-copy fresh headers to edit your playlists."
        )
    author = (playlist or {}).get("author") or {}
    who = author.get("name") if isinstance(author, dict) else None
    suffix = f" — it's owned by {who}" if who else ""
    raise RuntimeError("You can only edit playlists you own on YouTube Music" + suffix + ".")


def find_set_video_ids(playlist_response, video_id):
    """Return the `setVideoId`s of every track in a get_playlist() response whose
    `videoId` matches (a song can appear more than once in a playlist)."""
    set_video_ids = []
    for track in (playlist_response or {}).get("tracks") or []:
        if not isinstance(track, dict):
            continue
        if track.get("videoId") == video_id and track.get("setVideoId"):
            set_video_ids.append(track["setVideoId"])
    return set_video_ids


def find_repeat_items(playlist_response):
    """From a get_playlist() response, the `{videoId, setVideoId}` of every *extra*
    occurrence of a song listed more than once — i.e. all but the first appearance, in
    playlist order. These are the items to delete to de-duplicate the playlist."""
    seen = set()
    extras = []
    for track in (playlist_response or {}).get("tracks") or []:
        if not isinstance(track, dict):
            continue
        video_id = track.get("videoId")
        set_video_id = track.get("setVideoId")
        if not video_id or not set_video_id:
            continue
        if video_id in seen:
            extras.append({"videoId": video_id, "setVideoId": set_video_id})
        else:
            seen.add(video_id)
    return extras


def dedupe_local_tracks(pl_data):
    """Keep only the first cached track per song id (mirrors a YouTube de-dup). The
    `videos` set is already unique, so only `tracks` needs trimming."""
    seen = set()
    kept = []
    for track in pl_data.get("tracks") or []:
        identity = _track_video_id(track)
        if identity:
            if identity in seen:
                continue
            seen.add(identity)
        kept.append(track)
    pl_data["tracks"] = kept


def addable_target_playlists(saved_playlists, video_id):
    """Saved YouTube playlists that don't already contain `video_id`, as
    `[{"key", "id", "name"}, ...]` sorted by name. Spotify playlists are excluded
    (this auth can only write YouTube Music)."""
    targets = []
    for key, pl_data in (saved_playlists or {}).items():
        if not isinstance(pl_data, dict):
            continue
        if pl_data.get("source", "youtube") != "youtube":
            continue
        playlist_id = pl_data.get("id")
        if not playlist_id:
            continue
        if playlist_contains_video(pl_data, video_id):
            continue
        targets.append({"key": key, "id": playlist_id, "name": pl_data.get("name") or "Unnamed Playlist"})
    targets.sort(key=lambda target: target["name"].lower())
    return targets


def playlist_contains_video(pl_data, video_id):
    if video_id in _as_id_set(pl_data.get("videos")):
        return True
    return any(_track_video_id(track) == video_id for track in pl_data.get("tracks") or [])


def apply_local_add(pl_data, track, video_id):
    """Reflect a successful add in the in-memory playlist (videos set + tracks list)."""
    videos = _as_id_set(pl_data.get("videos"))
    videos.add(video_id)
    pl_data["videos"] = videos

    tracks = pl_data.setdefault("tracks", [])
    if not any(_track_video_id(existing) == video_id for existing in tracks):
        tracks.append(dict(track or {}))


def apply_local_remove(pl_data, video_id):
    """Reflect a successful remove in the in-memory playlist."""
    videos = _as_id_set(pl_data.get("videos"))
    videos.discard(video_id)
    pl_data["videos"] = videos
    pl_data["tracks"] = [
        track for track in pl_data.get("tracks") or [] if _track_video_id(track) != video_id
    ]


def _track_video_id(track):
    if not isinstance(track, dict):
        return None
    return track.get("videoId") or track.get("id")


def _as_id_set(videos):
    if isinstance(videos, set):
        return set(videos)
    if isinstance(videos, (list, tuple)):
        return set(videos)
    return set()


def _response_succeeded(response):
    if isinstance(response, str):
        return "SUCCEEDED" in response
    if isinstance(response, dict):
        return "SUCCEEDED" in str(response.get("status") or "")
    return False


def _describe_failure(action, response):
    return f"YouTube Music did not confirm it could {action}. Response: {response}"
