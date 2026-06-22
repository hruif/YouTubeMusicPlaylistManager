import { memo, useEffect, useState } from "react";
import { useVirtual } from "../hooks/useVirtual";
import { ROW_H } from "../lib/format";
import { SongRow } from "./SongRow";
import type { CombinedSong } from "../lib/ytmusic";

// True while the window is actively being resized. Used to collapse the tall virtual spacer to just
// the visible rows during a drag — the spacer's height scales with the song count, and re-evaluating
// that huge scroll area every resize frame is what made resize lag grow with list size.
function useResizing(): boolean {
  const [resizing, setResizing] = useState(false);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const onResize = () => {
      setResizing(true);
      clearTimeout(timer);
      timer = setTimeout(() => setResizing(false), 160);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      clearTimeout(timer);
    };
  }, []);
  return resizing;
}

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
  const resizing = useResizing();
  // While resizing, cap the spacer to just past the visible rows so Chromium isn't re-evaluating a
  // 150k-px-tall scroll area each frame; restore the full height (for an accurate scrollbar) when the
  // drag settles. The scrollbar thumb briefly grows during the drag — an acceptable trade for smooth
  // resize, and invisible unless you're dragging.
  const innerHeight = (resizing ? Math.min(songs.length, v.end + 1) : songs.length) * ROW_H;
  return (
    // Hide the scrollbar while resizing: the collapsed spacer makes the thumb temporarily wrong, and
    // you're dragging the window, not scrolling, so there's nothing to lose.
    <div className={`song-scroll${resizing ? " resizing" : ""}`} ref={v.ref}>
      {songs.length === 0 ? (
        <p className="empty">{emptyMessage}</p>
      ) : (
        <div className="song-inner" style={{ height: innerHeight }}>
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
