import type { RefObject } from "react";
import type { CombinedSong } from "../lib/ytmusic";
import type { SongFilters, SortKey } from "../lib/settings";
import { FilterMenu } from "./FilterMenu";
import { SongList } from "./SongList";

const COLUMNS: { key: SortKey; label: string; className?: string }[] = [
  { key: "title", label: "Title" },
  { key: "artist", label: "Artist" },
  { key: "album", label: "Album" },
  { key: "count", label: "In playlists" },
  { key: "duration", label: "Time", className: "num" },
];

type Props = {
  searchRef: RefObject<HTMLInputElement | null>;
  query: string;
  onQueryChange: (q: string) => void;
  filters: SongFilters;
  onFiltersChange: (f: SongFilters) => void;
  sortKey: SortKey;
  sortAsc: boolean;
  onSort: (key: SortKey) => void;
  songs: CombinedSong[]; // all songs of the selected playlists
  visibleSongs: CombinedSong[]; // after search/filter/sort
  playlistNames: string[]; // selected playlists
  busy: boolean;
  activeIndex: number | null;
  selectedSongs: Set<string>;
  customNames: Record<string, string>;
  replaceNames: boolean;
  onSongClick: (e: React.MouseEvent, index: number) => void;
  onSongContextMenu: (e: React.MouseEvent, index: number) => void;
  onRefresh: () => void;
  onPlayAll: () => void;
  onPlaySelected: () => void;
  onAddSelected: () => void;
  onRemoveSelected: () => void;
  onNewPlaylist: () => void;
  onClearSelection: () => void;
};

// Shown when no playlist is selected: a stack of playlist cards and an arrow toward the sidebar.
function PickPlaylistArt() {
  return (
    <svg className="empty-art" width="170" height="104" viewBox="0 0 170 104" aria-hidden="true">
      <rect x="62" y="10" width="90" height="62" rx="9" className="art-back" transform="rotate(6 107 41)" />
      <rect x="54" y="18" width="90" height="62" rx="9" className="art-card" />
      <rect x="68" y="34" width="50" height="6" rx="3" className="art-line" />
      <rect x="68" y="47" width="62" height="6" rx="3" className="art-line" />
      <rect x="68" y="60" width="30" height="6" rx="3" className="art-line" />
      <path d="M112 56 L128 64 L112 72 Z" className="art-accent" />
      <path d="M44 88 C 30 88, 18 80, 12 66" className="art-arrow" strokeDasharray="3 5" />
      <path d="M6 70 L12 62 L18 71" className="art-arrow" />
    </svg>
  );
}

// The bar above the song list. Normally it describes what's shown and offers Refresh / Play all;
// with songs selected it switches to actions on the selection.
function ContextBar(p: Props) {
  const n = p.selectedSongs.size;
  if (n > 0) {
    return (
      <div className="context-bar" role="toolbar" aria-label="Selected songs">
        <strong>{n} selected</strong>
        <span className="grow-input" />
        <button className="small" disabled={p.busy} onClick={p.onPlaySelected}>▶ Play</button>
        <button className="small" disabled={p.busy} onClick={p.onAddSelected}>Add to…</button>
        <button className="small" disabled={p.busy} onClick={p.onRemoveSelected}>Remove from…</button>
        <button className="small" disabled={p.busy} onClick={p.onNewPlaylist}>New playlist</button>
        <button className="small icon-btn" aria-label="Clear selection" title="Clear selection (Esc)" onClick={p.onClearSelection}>✕</button>
      </div>
    );
  }
  if (p.playlistNames.length === 0) return null;
  const shown = p.visibleSongs.length;
  const total = p.songs.length;
  return (
    <div className="context-bar" role="toolbar" aria-label="Playlists">
      <span className="context-summary" title={p.playlistNames.join(", ")}>
        {p.playlistNames.join(", ")} · {shown === total ? `${total} songs` : `${shown} of ${total} songs`}
      </span>
      <button className="small" disabled={p.busy} title="Load the latest songs for these playlists (⌘R)" onClick={p.onRefresh}>↻ Refresh</button>
      <button className="small primary" disabled={p.busy || total === 0} title="Open these songs as a queue in YouTube Music" onClick={p.onPlayAll}>▶ Play all</button>
    </div>
  );
}

export function SongPane(p: Props) {
  const filtering = p.query.trim() !== "" || p.filters.duplicates || p.filters.unavailable;
  const empty =
    p.playlistNames.length === 0 ? (
      <div className="empty empty-center">
        <PickPlaylistArt />
        <p className="empty-title">Pick a playlist to see its songs</p>
        <p className="empty-body">Select one or more on the left. Songs in several show up once.</p>
      </div>
    ) : p.songs.length === 0 ? (
      <p className="empty empty-center">{p.busy ? "Loading songs…" : "These playlists have no songs."}</p>
    ) : (
      <div className="empty empty-center">
        <p>No songs match.</p>
        {filtering && (
          <button
            className="small"
            onClick={() => {
              p.onQueryChange("");
              p.onFiltersChange({ duplicates: false, unavailable: false });
            }}
          >
            Clear search and filters
          </button>
        )}
      </div>
    );

  return (
    <section className="songpane" aria-label="Songs">
      <div className="searchbar">
        <input
          spellCheck={false}
          autoCorrect="off"
          autoCapitalize="off"
          ref={p.searchRef}
          className="search"
          type="search"
          aria-label="Search songs"
          placeholder="Search songs…  (⌘F)"
          value={p.query}
          onChange={(e) => p.onQueryChange(e.currentTarget.value)}
        />
        <FilterMenu filters={p.filters} onChange={p.onFiltersChange} />
      </div>
      <ContextBar {...p} />

      <div className="song-head" role="row" hidden={p.playlistNames.length === 0}>
        {COLUMNS.map((c) => {
          const sorted = p.sortKey === c.key;
          return (
            <div key={c.key} role="columnheader" aria-sort={sorted ? (p.sortAsc ? "ascending" : "descending") : "none"} className={c.className}>
              <button className="col" onClick={() => p.onSort(c.key)}>
                {c.label}
                {sorted && <span aria-hidden="true">{p.sortAsc ? " ▲" : " ▼"}</span>}
              </button>
            </div>
          );
        })}
      </div>
      <SongList
        songs={p.visibleSongs}
        empty={empty}
        activeIndex={p.activeIndex}
        selectedSongs={p.selectedSongs}
        customNames={p.customNames}
        replaceNames={p.replaceNames}
        onSongClick={p.onSongClick}
        onSongContextMenu={p.onSongContextMenu}
      />
    </section>
  );
}
