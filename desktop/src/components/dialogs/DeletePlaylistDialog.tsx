import { useState } from "react";
import type { Playlist } from "../../lib/ytmusic";
import { Overlay } from "../Overlay";

// Hardened delete: the playlist name must be typed to enable Delete.
export function DeletePlaylistDialog({
  playlist,
  cachedCount,
  onDelete,
  onClose,
}: {
  playlist: Playlist;
  cachedCount: number | undefined; // undefined = songs never loaded
  onDelete: () => void;
  onClose: () => void;
}) {
  const [text, setText] = useState("");
  const matches = text.trim() === playlist.title.trim();
  return (
    <Overlay title={`Delete “${playlist.title}”?`} onClose={onClose}>
      <p className="dialog-text warn">
        This permanently deletes the playlist from your YouTube Music account.
      </p>
      <p className="dialog-text">
        {cachedCount !== undefined
          ? `Its ${cachedCount} songs are kept in “Recently deleted,” so you can recreate it.`
          : "Its songs haven’t been loaded, so it can’t be recreated later. Select it in the sidebar first if you want that."}
      </p>
      <p className="dialog-text" style={{ margin: "10px 0 4px" }}>
        Type <strong>{playlist.title}</strong> to confirm:
      </p>
      <input
        spellCheck={false}
        autoCorrect="off"
        autoCapitalize="off"
        autoFocus
        aria-label="Playlist name to confirm"
        value={text}
        placeholder={playlist.title}
        onChange={(e) => setText(e.currentTarget.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            // Enter only deletes once the name matches (the safeguard); otherwise it cancels.
            if (matches) onDelete();
            else onClose();
          }
        }}
        className="full-width"
      />
      <div className="dialog-actions">
        <button className="primary" onClick={onClose}>Cancel</button>
        <button className="danger" disabled={!matches} onClick={onDelete}>Delete</button>
      </div>
    </Overlay>
  );
}
