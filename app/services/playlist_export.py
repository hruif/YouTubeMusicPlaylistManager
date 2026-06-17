"""Build an exportable CSV snapshot of a playlist's tracks.

Pure formatting (title/artist/source/id); the controller owns the file dialog + write.
"""
import csv
import io


def build_csv(tracks):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Artist", "Source", "ID"])
    for track in tracks or []:
        if not isinstance(track, dict):
            continue
        writer.writerow([
            track.get("title") or "",
            track.get("artist") or "",
            track.get("source") or "",
            track.get("videoId") or track.get("id") or track.get("trackId") or "",
        ])
    return output.getvalue()
