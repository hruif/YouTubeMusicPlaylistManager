"""QueueService: the non-UI YouTube Music temporary-playlist orchestration.

Extracted from the UI controller (service-object step, part 2). It performs the
ytmusicapi work — create a private playlist seeded with one song, add the rest in
adaptive chunks, delete playlists — given a queue `client` and a `set_status(text)`
progress callback. The Tk progress windows, threading, and message boxes stay in
the controller; this layer is free of tkinter.
"""
import contextlib
from datetime import datetime


class QueueService:
    def __init__(self, youtube_account, chunk_size):
        self._youtube_account = youtube_account
        self._chunk_size = chunk_size

    def create_temp_playlist(self, client, video_ids, source_playlists, set_status):
        """Create a private temporary playlist from video_ids (already deduped, preferred seed
        first). Returns (title, temp_playlist_id, skipped_video_ids). Raises on failure."""
        if not video_ids:
            raise RuntimeError(
                "No cached YouTube songs were found in the selected playlists. "
                "Update the selected playlists, then try again."
            )

        timestamp = datetime.now().strftime("%Y-%m-%d %H.%M")
        title = f"Playlist Manager Queue {timestamp}"
        description = "Temporary private playlist created by YouTube Music Playlist Manager."

        temp_playlist_id, remaining_video_ids, seeded_count, seed_error = self._create_seeded(
            client, title, description, video_ids, set_status
        )

        try:
            added_count, skipped_video_ids = self._add_video_ids(
                client, temp_playlist_id, remaining_video_ids, set_status
            )
        except Exception:
            self.best_effort_delete(client, temp_playlist_id)
            raise

        if seeded_count + added_count == 0:
            self.best_effort_delete(client, temp_playlist_id)
            raise RuntimeError(self._no_songs_added_error_message(seed_error, skipped_video_ids))

        self._youtube_account.remember_temporary_playlist(
            temp_playlist_id,
            title,
            [
                {"id": playlist["id"], "name": playlist["name"], "source": playlist["source"]}
                for playlist in source_playlists
            ],
        )
        return title, temp_playlist_id, skipped_video_ids

    def delete_temp_playlists(self, client, records, set_status):
        """Delete each record's playlist. Returns (deleted_ids, failed) where failed is a list
        of (record, exception)."""
        deleted_ids = []
        failed = []
        for index, record in enumerate(records, start=1):
            set_status(f"Deleting {index} of {len(records)}: {record.title}")
            try:
                response = client.delete_playlist(record.playlist_id)
                if isinstance(response, dict) and "status" in response and "SUCCEEDED" not in response["status"]:
                    raise RuntimeError(response)
                deleted_ids.append(record.playlist_id)
            except Exception as e:
                failed.append((record, e))
        return deleted_ids, failed

    def best_effort_delete(self, client, playlist_id):
        with contextlib.suppress(Exception):
            client.delete_playlist(playlist_id)

    def _create_seeded(self, client, title, description, video_ids, set_status):
        seed_errors = []
        for index, seed_video_id in enumerate(video_ids):
            set_status(f"Creating private playlist with seed song {index + 1} of {len(video_ids)}...")
            try:
                temp_playlist_id = client.create_playlist(
                    title,
                    description,
                    privacy_status="PRIVATE",
                    video_ids=[seed_video_id],
                )
                if not isinstance(temp_playlist_id, str) or not temp_playlist_id:
                    raise RuntimeError(temp_playlist_id)
                remaining_video_ids = video_ids[:index] + video_ids[index + 1:]
                return temp_playlist_id, remaining_video_ids, 1, None
            except Exception as ytmusic_error:
                seed_errors.append(f"{seed_video_id}: {ytmusic_error}")

        error_details = " | ".join(seed_errors[:3])
        if len(seed_errors) > 3:
            error_details += f" | {len(seed_errors) - 3} more seed errors"
        raise RuntimeError(
            "Could not create the temporary playlist with ytmusicapi browser auth. "
            "Refresh the queue headers in Settings, then try again. "
            f"YouTube Music error: {error_details or 'all seed songs were rejected'}"
        )

    def _add_video_ids(self, client, temp_playlist_id, video_ids, set_status):
        added_count = 0
        skipped_video_ids = []
        chunks = list(self._chunks(video_ids, self._chunk_size))
        for index, chunk in enumerate(chunks, start=1):
            set_status(f"Adding songs {index} of {len(chunks)}...")
            added, skipped = self._add_chunk_adaptive(
                client, temp_playlist_id, chunk, set_status, f"batch {index} of {len(chunks)}"
            )
            added_count += added
            skipped_video_ids.extend(skipped)
        return added_count, skipped_video_ids

    def _add_chunk_adaptive(self, client, temp_playlist_id, video_ids, set_status, label):
        if not video_ids:
            return 0, []

        try:
            response = client.add_playlist_items(temp_playlist_id, videoIds=video_ids)
            if self._response_succeeded(response):
                return len(video_ids), []
            raise RuntimeError(response)
        except Exception as e:
            if len(video_ids) == 1:
                return 0, [{"video_id": video_ids[0], "error": str(e)}]

            middle = max(1, len(video_ids) // 2)
            set_status(f"Retrying smaller song groups from {label}...")
            left_added, left_skipped = self._add_chunk_adaptive(
                client, temp_playlist_id, video_ids[:middle], set_status, label
            )
            right_added, right_skipped = self._add_chunk_adaptive(
                client, temp_playlist_id, video_ids[middle:], set_status, label
            )
            return left_added + right_added, left_skipped + right_skipped

    @staticmethod
    def _no_songs_added_error_message(seed_error, skipped_video_ids):
        base = "No songs could be added to the temporary playlist."
        details = []
        seed_error = str(seed_error or "").strip()
        if seed_error:
            details.append(f"create-with-song error: {seed_error}")

        distinct_add_errors = []
        for item in skipped_video_ids or []:
            error_text = str((item or {}).get("error") or "").strip()
            if error_text and error_text not in distinct_add_errors:
                distinct_add_errors.append(error_text)
            if len(distinct_add_errors) >= 3:
                break
        details.extend(f"add error: {error_text}" for error_text in distinct_add_errors)

        if details:
            return f"{base} YouTube reported: " + " | ".join(details)
        return base

    @staticmethod
    def _response_succeeded(response):
        if isinstance(response, str):
            return "SUCCEEDED" in response
        if isinstance(response, dict):
            return "SUCCEEDED" in str(response.get("status") or "")
        return False

    @staticmethod
    def _chunks(items, size):
        if size <= 0:
            raise ValueError("Chunk size must be greater than zero.")
        for start in range(0, len(items), size):
            yield items[start:start + size]
