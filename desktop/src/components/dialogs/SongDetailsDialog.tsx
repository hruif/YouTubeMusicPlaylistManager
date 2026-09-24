import { useState } from "react";
import type { CombinedSong, Playlist } from "../../lib/ytmusic";
import { formatDuration } from "../../lib/format";
import { Overlay } from "../Overlay";

export function SongDetailsDialog({
  song,
  customName,
  membership,
  addTargets,
  editable,
  busy,
  onSaveCustomName,
  onOpenSong,
  onOpenPlaylist,
  onRemoveFrom,
  onAddTo,
  onClose,
}: {
  song: CombinedSong;
  customName: string;
  membership: Playlist[]; // loaded playlists containing the song
  addTargets: Playlist[]; // editable sidebar playlists it isn't in
  editable: Set<string>;
  busy: boolean;
  onSaveCustomName: (name: string) => void;
  onOpenSong: () => void;
  onOpenPlaylist: (id: string) => void;
  onRemoveFrom: (p: Playlist) => void;
  onAddTo: (p: Playlist) => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState(customName);
  const [target, setTarget] = useState("");
  const facts = [song.artist, song.album, formatDuration(song.duration)].filter(Boolean).join(" · ");
  return (
    <Overlay title={song.title} onClose={onClose}>
      <div className="row-gap" style={{ alignItems: "center", marginBottom: 10 }}>
        <span className="muted grow-input">{facts || "Unknown artist"}</span>
        <button className="small" onClick={onOpenSong}>Open in YouTube Music</button>
      </div>

      <p className="dialog-label">Custom name</p>
      <div className="row-gap">
        <input
          spellCheck={false}
          autoCorrect="off"
          autoCapitalize="off"
          className="grow-input"
          aria-label="Custom name"
          placeholder="Your own name for this song (searchable)"
          value={draft}
          onChange={(e) => setDraft(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && onSaveCustomName(draft)}
        />
        <button className="primary" onClick={() => onSaveCustomName(draft)}>Save</button>
        {draft && (
          <button
            onClick={() => {
              setDraft("");
              onSaveCustomName("");
            }}
          >
            Clear
          </button>
        )}
      </div>

      <p className="dialog-label" style={{ marginTop: 14 }}>In {membership.length} playlist{membership.length === 1 ? "" : "s"}</p>
      <div className="panel scroll-32">
        {membership.length === 0 ? (
          <p className="empty">Not in any selected playlist.</p>
        ) : (
          membership.map((p) => (
            <div key={p.id} className="pl-row">
              <span className="pl-title">{p.title}{editable.has(p.id) ? "" : " (read-only)"}</span>
              <button className="small" onClick={() => onOpenPlaylist(p.id)}>Open</button>
              {editable.has(p.id) && (
                <button className="small danger" disabled={busy} onClick={() => onRemoveFrom(p)}>Remove</button>
              )}
            </div>
          ))
        )}
      </div>

      <p className="dialog-label" style={{ marginTop: 14 }}>Add to a playlist</p>
      <div className="row-gap">
        <select className="grow-input" aria-label="Playlist to add to" value={target} onChange={(e) => setTarget(e.currentTarget.value)}>
          <option value="">{addTargets.length ? "Choose a playlist…" : "No sidebar playlists you can edit"}</option>
          {addTargets.map((p) => (
            <option key={p.id} value={p.id}>{p.title}</option>
          ))}
        </select>
        <button
          className="primary"
          disabled={busy || !target}
          onClick={() => {
            const p = addTargets.find((x) => x.id === target);
            if (p) onAddTo(p);
            setTarget("");
          }}
        >
          Add
        </button>
      </div>
    </Overlay>
  );
}
