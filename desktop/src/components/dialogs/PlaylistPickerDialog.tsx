import { useState } from "react";
import type { Playlist } from "../../lib/ytmusic";
import { Overlay } from "../Overlay";

// Pick a target playlist for "Add to…" / "Remove from…". `meta` renders the right-hand count.
export function PlaylistPickerDialog({
  title,
  playlists,
  filterable,
  emptyText,
  meta,
  onPick,
  onClose,
}: {
  title: string;
  playlists: Playlist[];
  filterable: boolean;
  emptyText: string;
  meta: (p: Playlist) => string | null;
  onPick: (p: Playlist) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const shown = q ? playlists.filter((p) => p.title.toLowerCase().includes(q)) : playlists;
  return (
    <Overlay title={title} onClose={onClose}>
      {filterable && playlists.length > 0 && (
        <input
          spellCheck={false}
          autoCorrect="off"
          autoCapitalize="off"
          aria-label="Filter playlists"
          placeholder="Filter playlists…"
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          className="full-width"
        />
      )}
      {shown.length === 0 ? (
        <p className="empty">{playlists.length === 0 ? emptyText : "No playlists match."}</p>
      ) : (
        <div className="panel scroll-50">
          {shown.map((p) => {
            const m = meta(p);
            return (
              <button key={p.id} className="pl-row pl-pick" onClick={() => onPick(p)}>
                <span className="pl-title">{p.title}</span>
                {m && <span className="pl-meta">{m}</span>}
              </button>
            );
          })}
        </div>
      )}
    </Overlay>
  );
}
