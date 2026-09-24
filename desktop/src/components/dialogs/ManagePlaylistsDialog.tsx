import { useState } from "react";
import type { Playlist } from "../../lib/ytmusic";
import type { PlaylistSort } from "../../lib/settings";
import { Overlay } from "../Overlay";
import { PlaylistSortSelect } from "../Sidebar";

export function ManagePlaylistsDialog({
  playlists,
  totalCount,
  shown,
  busy,
  playlistSort,
  onSortChange,
  onSetShown,
  onAddByUrl,
  onRefreshList,
  onImportSpotify,
  onOpenDetails,
  onContextMenu,
  onClose,
}: {
  playlists: Playlist[]; // sorted, queues excluded
  totalCount: number;
  shown: Set<string>;
  busy: boolean;
  playlistSort: PlaylistSort;
  onSortChange: (sort: PlaylistSort) => void;
  onSetShown: (id: string, show: boolean) => void;
  onAddByUrl: (url: string) => void;
  onRefreshList: () => void;
  onImportSpotify: () => void;
  onOpenDetails: (e: React.MouseEvent, p: Playlist) => void;
  onContextMenu: (e: React.MouseEvent, p: Playlist) => void;
  onClose: () => void;
}) {
  const [url, setUrl] = useState("");
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const list = q ? playlists.filter((p) => p.title.toLowerCase().includes(q)) : playlists;
  const add = () => url.trim() && !busy && onAddByUrl(url);

  return (
    <Overlay title="Manage playlists" onClose={onClose}>
      <p className="dialog-label">Add a playlist</p>
      <p className="dialog-hint">
        Paste a link to any public YouTube or YouTube Music playlist. You can only edit it if it’s yours.
      </p>
      <div className="row-gap">
        <input
          spellCheck={false}
          autoCorrect="off"
          autoCapitalize="off"
          className="grow-input"
          aria-label="Playlist link"
          placeholder="https://music.youtube.com/playlist?list=…"
          value={url}
          onChange={(e) => setUrl(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
        />
        <button className="primary" disabled={busy || !url.trim()} onClick={add}>Add</button>
        <button disabled={busy} onClick={onImportSpotify}>Import from Spotify</button>
      </div>

      <div className="dialog-section-head">
        <span className="dialog-label grow-input">Your playlists</span>
        <PlaylistSortSelect value={playlistSort} onChange={onSortChange} />
        <button
          className="small"
          disabled={busy}
          title="Re-fetch your playlists from YouTube Music (e.g. after creating or deleting one elsewhere)"
          onClick={onRefreshList}
        >
          Refresh list
        </button>
      </div>
      <p className="dialog-hint">
        Check the playlists you want in the sidebar. Double-click for details, or right-click for more.
        {` ${shown.size} of ${totalCount} shown.`}
      </p>
      <input
        spellCheck={false}
        autoCorrect="off"
        autoCapitalize="off"
        aria-label="Filter playlists"
        placeholder="Filter…"
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        className="full-width"
      />
      <div className="panel scroll-50">
        {list.map((p) => (
          <label
            key={p.id}
            className="pl-row"
            onDoubleClick={(e) => onOpenDetails(e, p)}
            onContextMenu={(e) => onContextMenu(e, p)}
          >
            <input type="checkbox" checked={shown.has(p.id)} onChange={(e) => onSetShown(p.id, e.currentTarget.checked)} />
            <span className="pl-title">{p.title}</span>
          </label>
        ))}
        {list.length === 0 && <p className="empty">{q ? "No playlists match." : "No playlists yet."}</p>}
      </div>
    </Overlay>
  );
}
