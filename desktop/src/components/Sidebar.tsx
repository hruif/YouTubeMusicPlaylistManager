import type { Playlist, Track } from "../lib/ytmusic";
import type { PlaylistSort } from "../lib/settings";
import { relativeAge } from "../lib/format";
import { useDoubleClick } from "../hooks/useDoubleClick";

type Props = {
  playlists: Playlist[]; // sidebar playlists, already sorted
  tracksByPlaylist: Record<string, Track[]>;
  updatedAt: Record<string, number>;
  selected: Set<string>;
  playlistSort: PlaylistSort;
  loading: Record<string, { loaded: number; total?: number }>;
  isStale: (id: string) => boolean;
  onSortChange: (sort: PlaylistSort) => void;
  onSelectAll: () => void;
  onClear: () => void;
  onToggle: (id: string) => void;
  onHide: (id: string) => void;
  onOpenDetails: (e: React.MouseEvent, p: Playlist) => void;
  onContextMenu: (e: React.MouseEvent, p: Playlist) => void;
  onManage: () => void;
};

// Loading indicator in place of a playlist's song count: a pie filling up as pages arrive, or a
// spinning ring when YouTube didn't say how many songs to expect.
function LoadPie({ loaded, total }: { loaded: number; total?: number }) {
  const label = total ? `Loading ${loaded} of ${total} songs` : "Loading songs";
  if (!total) return <span className="load-spin" role="img" aria-label={label} title={label} />;
  const frac = Math.min(1, loaded / total);
  // An r=7 circle stroked 14 wide paints a solid disc; the dash length is the slice that's filled.
  return (
    <svg className="load-pie" viewBox="0 0 32 32" role="img" aria-label={label}>
      <title>{label}</title>
      <circle cx="16" cy="16" r="14" className="load-pie-bg" />
      <circle
        cx="16"
        cy="16"
        r="7"
        className="load-pie-fill"
        strokeDasharray={`${(frac * 2 * Math.PI * 7).toFixed(2)} ${(2 * Math.PI * 7).toFixed(2)}`}
        transform="rotate(-90 16 16)"
      />
    </svg>
  );
}

export function PlaylistSortSelect({ value, onChange }: { value: PlaylistSort; onChange: (sort: PlaylistSort) => void }) {
  return (
    <select className="small" value={value} onChange={(e) => onChange(e.currentTarget.value as PlaylistSort)} aria-label="Sort playlists" title="Sort playlists">
      <option value="name">A–Z</option>
      <option value="updated">Updated</option>
      <option value="count">Size</option>
    </select>
  );
}

export function Sidebar(p: Props) {
  // One button that flips between the two, so the header stays on one line.
  const allSelected = p.playlists.length > 0 && p.playlists.every((pl) => p.selected.has(pl.id));
  const isDoubleClick = useDoubleClick();
  return (
    <section className="sidebar" aria-label="Playlists">
      <div className="sidebar-head">
        <strong>Playlists ({p.playlists.length})</strong>
        <PlaylistSortSelect value={p.playlistSort} onChange={p.onSortChange} />
        <button className="small" disabled={p.playlists.length === 0} onClick={allSelected ? p.onClear : p.onSelectAll}>
          {allSelected ? "Clear" : "Select all"}
        </button>
      </div>
      <div className="panel list">
        {p.playlists.map((pl) => {
          const tracks = p.tracksByPlaylist[pl.id];
          const stale = p.isStale(pl.id);
          const load = p.loading[pl.id];
          return (
            <div
              key={pl.id}
              className="pl-row"
              onClick={(e) => isDoubleClick(pl.id) && p.onOpenDetails(e, pl)}
              onContextMenu={(e) => p.onContextMenu(e, pl)}
            >
              <input type="checkbox" aria-label={pl.title} checked={p.selected.has(pl.id)} onChange={() => p.onToggle(pl.id)} />
              <span className="pl-title" onClick={() => p.onToggle(pl.id)}>{pl.title}</span>
              {load ? (
                <LoadPie loaded={load.loaded} total={load.total} />
              ) : (
                <>
                  {stale && (
                    <span
                      className={`dot ${tracks ? "stale" : "none"}`}
                      title={tracks ? `Updated ${relativeAge(p.updatedAt[pl.id])}` : "Songs not loaded yet"}
                    />
                  )}
                  {tracks && <span className="pl-meta">{tracks.length}</span>}
                </>
              )}
              <button className="pl-hide" aria-label={`Remove ${pl.title} from sidebar`} title="Remove from sidebar" onClick={() => p.onHide(pl.id)}>×</button>
            </div>
          );
        })}
        {p.playlists.length === 0 && (
          <div className="empty sidebar-empty">
            <span>No playlists added yet.</span>
            <button className="small" onClick={p.onManage}>Add playlists</button>
          </div>
        )}
      </div>
    </section>
  );
}
