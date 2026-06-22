import { memo } from "react";
import { useVirtual } from "../hooks/useVirtual";
import { ROW_H } from "../lib/format";
import { SongRow } from "./SongRow";
import type { CombinedSong } from "../lib/ytmusic";

type Props = {
  songs: CombinedSong[]; // already filtered/sorted (visibleSongs)
  emptyMessage: string;
  selectedSongs: Set<string>;
  customNames: Record<string, string>;
  replaceNames: boolean;
  onSongClick: (e: React.MouseEvent, index: number) => void;
  onSongContextMenu: (e: React.MouseEvent, index: number) => void;
};

// The scroll/resize-driven virtualization state (scrollTop, container height) lives HERE rather than
// in App. That keeps a window resize or a scroll from re-rendering the entire (large) App component
// every frame — only this subtree and the handful of visible rows reconcile, which is the main lever
// for smooth resizing/scrolling. Memoized so unrelated App state changes don't re-render it.
export const SongList = memo(function SongList({
  songs,
  emptyMessage,
  selectedSongs,
  customNames,
  replaceNames,
  onSongClick,
  onSongContextMenu,
}: Props) {
  const v = useVirtual(songs.length);
  return (
    <div className="song-scroll" ref={v.ref}>
      {songs.length === 0 ? (
        <p className="empty">{emptyMessage}</p>
      ) : (
        <div className="song-inner" style={{ height: songs.length * ROW_H }}>
          {songs.slice(v.start, v.end).map((s, idx) => {
            const i = v.start + idx;
            return (
              <SongRow
                key={s.videoId}
                song={s}
                index={i}
                zebra={i % 2 === 1}
                selected={selectedSongs.has(s.videoId)}
                customName={customNames[s.videoId]}
                replaceName={replaceNames}
                onClick={onSongClick}
                onContextMenu={onSongContextMenu}
              />
            );
          })}
        </div>
      )}
    </div>
  );
});
