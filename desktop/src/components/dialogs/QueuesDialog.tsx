import type { LibraryCache } from "../../lib/cache";
import { relativeAge } from "../../lib/format";
import { Overlay } from "../Overlay";

export function QueuesDialog({
  queues,
  titleById,
  busy,
  onOpen,
  onDelete,
  onDeleteAll,
  onClose,
}: {
  queues: LibraryCache["tempPlaylists"];
  titleById: Map<string, string>;
  busy: boolean;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onDeleteAll: () => void;
  onClose: () => void;
}) {
  return (
    <Overlay title="Queues" onClose={onClose}>
      <p className="dialog-hint">
        Temporary playlists made by “Play in YouTube Music”. They stay on your account until you delete them.
      </p>
      {queues.length === 0 ? (
        <p className="empty">No queues.</p>
      ) : (
        <>
          <div className="panel scroll-50">
            {queues.map((t) => (
              <div key={t.id} className="pl-row">
                <span className="pl-title">{titleById.get(t.id) ?? t.title}</span>
                <span className="pl-meta">{relativeAge(t.createdAt)}</span>
                <button className="small" onClick={() => onOpen(t.id)}>Open</button>
                <button className="small" disabled={busy} onClick={() => onDelete(t.id)}>Delete</button>
              </div>
            ))}
          </div>
          <div className="dialog-actions">
            <button className="danger" disabled={busy} onClick={onDeleteAll}>Delete all</button>
          </div>
        </>
      )}
    </Overlay>
  );
}
