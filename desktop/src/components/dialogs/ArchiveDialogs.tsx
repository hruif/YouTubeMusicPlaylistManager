import type { DeletedPlaylist, LibraryCache } from "../../lib/cache";
import { relativeAge } from "../../lib/format";
import { Overlay } from "../Overlay";

type RemovedSong = LibraryCache["removedSongs"][string][number];

export function RemovedSongsDialog({
  songs,
  onOpenSong,
  onSearch,
  onClose,
}: {
  songs: RemovedSong[];
  onOpenSong: (videoId: string) => void;
  onSearch: (s: RemovedSong) => void;
  onClose: () => void;
}) {
  return (
    <Overlay title="Removed songs" onClose={onClose}>
      <p className="dialog-hint">Songs that have left this playlist, whether you removed them here or elsewhere.</p>
      <div className="panel scroll-50">
        {songs.map((t, i) => (
          <div key={i} className="pl-row">
            <span className="pl-title">{t.title}</span>
            <span className="pl-meta">{t.artist} · {relativeAge(t.removedAt)}</span>
            {t.videoId ? (
              <button className="small" onClick={() => onOpenSong(t.videoId!)}>Open</button>
            ) : (
              <button className="small" onClick={() => onSearch(t)}>Search</button>
            )}
          </div>
        ))}
      </div>
    </Overlay>
  );
}

export function RecentlyDeletedDialog({
  deleted,
  busy,
  onRecreate,
  onForget,
  onClose,
}: {
  deleted: DeletedPlaylist[];
  busy: boolean;
  onRecreate: (d: DeletedPlaylist) => void;
  onForget: (d: DeletedPlaylist) => void;
  onClose: () => void;
}) {
  return (
    <Overlay title="Recently deleted" onClose={onClose}>
      <p className="dialog-hint">Playlists deleted in this app. Recreate makes a new playlist with the same songs.</p>
      {deleted.length === 0 ? (
        <p className="empty">Nothing here.</p>
      ) : (
        <div className="panel scroll-55">
          {deleted.map((d) => (
            <div key={`${d.id}-${d.deletedAt}`} className="pl-row">
              <span className="pl-title">{d.title}</span>
              <span className="pl-meta">{d.tracks.length} songs · {relativeAge(d.deletedAt)}</span>
              <button className="small" disabled={busy} onClick={() => onRecreate(d)}>Recreate</button>
              <button className="small" onClick={() => onForget(d)}>Forget</button>
            </div>
          ))}
        </div>
      )}
    </Overlay>
  );
}
