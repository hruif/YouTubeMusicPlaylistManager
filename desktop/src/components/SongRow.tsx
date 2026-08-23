import { memo } from "react";
import { formatPlaylistNames, ROW_H } from "../lib/format";
import type { CombinedSong } from "../lib/ytmusic";

type Props = {
  song: CombinedSong;
  index: number; // absolute position in the list (stable per song) → also the virtual top offset
  zebra: boolean;
  selected: boolean;
  customName?: string;
  replaceName: boolean; // true: show only the custom name; false: show custom + the real title
  onClick: (e: React.MouseEvent, index: number) => void;
  onContextMenu: (e: React.MouseEvent, index: number) => void;
};

// Memoized so unrelated state changes (modals, busy/status, scrolling) don't re-render every visible
// row — only rows whose own song/selection/customName (or the stable callbacks) change.
export const SongRow = memo(function SongRow({ song, index, zebra, selected, customName, replaceName, onClick, onContextMenu }: Props) {
  return (
    <div
      className={`song-row${zebra ? " zebra" : ""}${selected ? " selected" : ""}`}
      style={{ top: index * ROW_H }}
      onClick={(e) => onClick(e, index)}
      onContextMenu={(e) => onContextMenu(e, index)}
    >
      <div className="cell title-cell">
        {song.thumb ? (
          // If the cached CDN art URL fails (they can expire), fall back to the always-available
          // i.ytimg.com video thumbnail; if that also fails, drop the src so the .thumb grey box
          // shows instead of a broken-image icon. (A refresh re-fetches fresh art URLs.)
          <img
            className="thumb"
            src={song.thumb}
            loading="lazy"
            alt=""
            onError={(e) => {
              const img = e.currentTarget;
              const fallback = `https://i.ytimg.com/vi/${song.videoId}/default.jpg`;
              if (!img.dataset.fellBack && img.src !== fallback) {
                img.dataset.fellBack = "1";
                img.src = fallback;
              } else {
                img.removeAttribute("src");
              }
            }}
          />
        ) : (
          <span className="thumb" />
        )}
        {customName ? (
          <span className="ttext" title={song.title}>
            {customName}
            {!replaceName && <span className="real-alt"> · {song.title}</span>}
          </span>
        ) : (
          <span className="ttext">{song.title}</span>
        )}
      </div>
      <div className="cell muted">{song.artist}</div>
      <div className="cell muted" title={song.playlists.join(", ")}>
        {formatPlaylistNames(song.playlists)}
      </div>
    </div>
  );
});
