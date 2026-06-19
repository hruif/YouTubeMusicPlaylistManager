import { memo } from "react";
import { ROW_H } from "../lib/format";
import type { CombinedSong } from "../lib/ytmusic";

type Props = {
  song: CombinedSong;
  index: number; // absolute position in the list (stable per song) → also the virtual top offset
  zebra: boolean;
  selected: boolean;
  customName?: string;
  onClick: (e: React.MouseEvent, index: number) => void;
  onContextMenu: (e: React.MouseEvent, index: number) => void;
};

// Memoized so unrelated state changes (modals, busy/status, scrolling) don't re-render every visible
// row — only rows whose own song/selection/customName (or the stable callbacks) change.
export const SongRow = memo(function SongRow({ song, index, zebra, selected, customName, onClick, onContextMenu }: Props) {
  return (
    <div
      className={`song-row${zebra ? " zebra" : ""}${selected ? " selected" : ""}`}
      style={{ top: index * ROW_H }}
      onClick={(e) => onClick(e, index)}
      onContextMenu={(e) => onContextMenu(e, index)}
    >
      <div className="cell title-cell">
        {song.thumb ? <img className="thumb" src={song.thumb} loading="lazy" alt="" /> : <span className="thumb" />}
        <span className="ttext" title={customName ? song.title : undefined}>{customName || song.title}</span>
      </div>
      <div className="cell muted">{song.artist}</div>
      <div className="cell muted" title={song.playlists.join(", ")}>
        {song.playlists.length === 1 ? song.playlists[0] : `${song.playlists.length} playlists`}
      </div>
    </div>
  );
});
