import { useState } from "react";
import { Overlay } from "../Overlay";

export function CreatePlaylistDialog({
  songCount,
  busy,
  onCreate,
  onClose,
}: {
  songCount: number;
  busy: boolean;
  onCreate: (name: string) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const submit = () => name.trim() && !busy && onCreate(name.trim());
  return (
    <Overlay title={`New playlist from ${songCount} song${songCount === 1 ? "" : "s"}`} onClose={onClose}>
      <input
        spellCheck={false}
        autoCorrect="off"
        autoCapitalize="off"
        autoFocus
        aria-label="Playlist name"
        placeholder="Playlist name"
        value={name}
        onChange={(e) => setName(e.currentTarget.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        className="full-width"
      />
      <div className="dialog-actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" disabled={!name.trim()} onClick={submit}>Create</button>
      </div>
    </Overlay>
  );
}
