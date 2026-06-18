import { useEffect, useMemo, useRef, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getLibraryPlaylists,
  fetchTracksForPlaylists,
  combineFromCache,
  type Playlist,
  type CombinedSong,
} from "./lib/ytmusic";
import { loadCache, saveCache, EMPTY_CACHE, type LibraryCache } from "./lib/cache";
import "./App.css";

// Phase 1: read-only parity, cache-driven, polished. Virtualized song list, staleness, persisted
// selection/sort, search (Cmd+F), hide playlists, details with external links.

type SortKey = "title" | "artist" | "count";
const ROW_H = 30;
const STALE_MS = 7 * 24 * 3600 * 1000;

// --- small persisted UI state (selection/sort/filter) in localStorage (tiny, frequent writes) ---
type UiState = { selected: string[]; sortKey: SortKey; sortAsc: boolean; dupOnly: boolean };
const UI_KEY = "ytm.ui";
function loadUi(): UiState {
  const base: UiState = { selected: [], sortKey: "title", sortAsc: true, dupOnly: false };
  try {
    const raw = localStorage.getItem(UI_KEY);
    return raw ? { ...base, ...(JSON.parse(raw) as Partial<UiState>) } : base;
  } catch {
    return base;
  }
}

function relativeAge(ms?: number): string {
  if (!ms) return "never";
  const mins = Math.floor((Date.now() - ms) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// Virtualization: render only the rows in view.
function useVirtual(count: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [height, setHeight] = useState(600);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(() => setHeight(el.clientHeight));
    ro.observe(el);
    setHeight(el.clientHeight);
    return () => {
      el.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, []);
  const overscan = 10;
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - overscan);
  const end = Math.min(count, Math.ceil((scrollTop + height) / ROW_H) + overscan);
  return { ref, start, end };
}

function App() {
  const ui0 = useRef(loadUi()).current;
  const [status, setStatus] = useState("Starting…");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [cache, setCache] = useState<LibraryCache>({ ...EMPTY_CACHE });
  const [selected, setSelected] = useState<Set<string>>(() => new Set(ui0.selected));
  const [sortKey, setSortKey] = useState<SortKey>(ui0.sortKey);
  const [sortAsc, setSortAsc] = useState(ui0.sortAsc);
  const [dupOnly, setDupOnly] = useState(ui0.dupOnly);
  const [query, setQuery] = useState("");
  const [showManage, setShowManage] = useState(false);
  const [manageQuery, setManageQuery] = useState("");
  const [detail, setDetail] = useState<CombinedSong | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [menu, setMenu] = useState<{ x: number; y: number; items: { label: string; onClick: () => void }[] } | null>(null);

  function persist(next: LibraryCache) {
    setCache(next);
    void saveCache(next);
  }

  const openSong = (videoId: string) => void openUrl(`https://music.youtube.com/watch?v=${videoId}`);
  const openPlaylist = (id: string) => void openUrl(`https://music.youtube.com/playlist?list=${id}`);
  function openMenu(e: React.MouseEvent, items: { label: string; onClick: () => void }[]) {
    e.preventDefault();
    e.stopPropagation();
    setMenu({ x: Math.min(e.clientX, window.innerWidth - 190), y: e.clientY, items });
  }

  // Suppress the WebView's default right-click menu (reload/inspect) so we can use our own;
  // any left-click dismisses an open context menu.
  useEffect(() => {
    const onCtx = (e: MouseEvent) => e.preventDefault();
    const onClick = () => setMenu(null);
    window.addEventListener("contextmenu", onCtx);
    window.addEventListener("click", onClick);
    return () => {
      window.removeEventListener("contextmenu", onCtx);
      window.removeEventListener("click", onClick);
    };
  }, []);

  // Persist UI state on change.
  useEffect(() => {
    try {
      localStorage.setItem(UI_KEY, JSON.stringify({ selected: [...selected], sortKey, sortAsc, dupOnly }));
    } catch {
      /* ignore */
    }
  }, [selected, sortKey, sortAsc, dupOnly]);

  // Cmd/Ctrl+F focuses the song search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function refreshPlaylists(current: LibraryCache) {
    setBusy(true);
    setStatus("Refreshing playlist list…");
    try {
      const playlists = await getLibraryPlaylists();
      persist({ ...current, playlists });
      setStatus(`${playlists.length} playlists`);
    } catch (err) {
      setStatus(`Failed to refresh playlists: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return; // guard React StrictMode's double-invoke in dev
    started.current = true;
    (async () => {
      const cached = await loadCache();
      setCache(cached);
      setStatus("Signing in…");
      try {
        const names = await trySilentSignIn();
        if (names) {
          setSignedIn(true);
          setStatus(`${cached.playlists.length} playlists (cached)`);
          if (cached.playlists.length === 0) await refreshPlaylists(cached);
        } else {
          setStatus("Not signed in");
        }
      } catch (err) {
        setStatus(`Sign-in failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hidden = useMemo(() => new Set(cache.hidden), [cache.hidden]);
  const visiblePlaylists = useMemo(
    () => cache.playlists.filter((p) => !hidden.has(p.id)),
    [cache.playlists, hidden],
  );
  const titleToId = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of cache.playlists) m.set(p.title, p.id);
    return m;
  }, [cache.playlists]);

  function isStale(id: string): boolean {
    const t = cache.updatedAt[id];
    return !cache.tracksByPlaylist[id] || !t || Date.now() - t > STALE_MS;
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function setPlaylistHidden(id: string, hide: boolean) {
    const next = new Set(cache.hidden);
    if (hide) next.add(id);
    else next.delete(id);
    persist({ ...cache, hidden: [...next] });
    if (hide)
      setSelected((prev) => {
        const s = new Set(prev);
        s.delete(id);
        return s;
      });
  }

  const selectedPlaylists = useMemo(
    () => cache.playlists.filter((p) => selected.has(p.id)),
    [cache.playlists, selected],
  );
  const stalePlaylists = useMemo(
    () => visiblePlaylists.filter((p) => isStale(p.id)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visiblePlaylists, cache.updatedAt, cache.tracksByPlaylist],
  );

  async function runUpdate(list: Playlist[]) {
    if (list.length === 0) return;
    setBusy(true);
    setStatus(`Updating 0/${list.length}…`);
    try {
      const { tracksByPlaylist, failures } = await fetchTracksForPlaylists(list, 4, (done, total) =>
        setStatus(`Updating ${done}/${total}…`),
      );
      const now = Date.now();
      const updatedAt = { ...cache.updatedAt };
      for (const id of Object.keys(tracksByPlaylist)) updatedAt[id] = now;
      persist({
        ...cache,
        tracksByPlaylist: { ...cache.tracksByPlaylist, ...tracksByPlaylist },
        updatedAt,
      });
      const n = Object.keys(tracksByPlaylist).length;
      setStatus(failures.length ? `Updated ${n}; ${failures.length} failed (retry)` : `Updated ${n} playlist(s)`);
    } catch (err) {
      setStatus(`Update failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const songs = useMemo(
    () => combineFromCache(selectedPlaylists, cache.tracksByPlaylist),
    [selectedPlaylists, cache.tracksByPlaylist],
  );

  const visibleSongs = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = songs;
    if (q) filtered = filtered.filter((s) => s.title.toLowerCase().includes(q) || s.artist.toLowerCase().includes(q));
    if (dupOnly) filtered = filtered.filter((s) => s.playlists.length > 1);
    const copy = [...filtered];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "title") cmp = a.title.localeCompare(b.title);
      else if (sortKey === "artist") cmp = a.artist.localeCompare(b.artist);
      else cmp = a.playlists.length - b.playlists.length;
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [songs, query, dupOnly, sortKey, sortAsc]);

  const v = useVirtual(visibleSongs.length);

  function sortBy(key: SortKey) {
    if (sortKey === key) setSortAsc((a) => !a);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  }
  const arrow = (key: SortKey) => (sortKey === key ? (sortAsc ? " ▲" : " ▼") : "");

  const uncachedSelected = selectedPlaylists.filter((p) => !cache.tracksByPlaylist[p.id]).length;
  const manageList = cache.playlists.filter((p) =>
    p.title.toLowerCase().includes(manageQuery.trim().toLowerCase()),
  );

  return (
    <main className="app">
      <header className="toolbar">
        <h1>YouTube Music Manager</h1>
        <span className="status">{status}</span>
        <span className="grow" />
        <span className="actions">
          {signedIn && <button disabled={busy} onClick={() => setShowManage(true)}>Manage playlists</button>}
          {signedIn && <button disabled={busy} onClick={() => refreshPlaylists(cache)}>Refresh list</button>}
          {signedIn ? (
            <button
              disabled={busy}
              onClick={async () => {
                await signOut();
                setSignedIn(false);
                setSelected(new Set());
                setStatus("Signed out");
              }}
            >
              Sign out
            </button>
          ) : (
            <button
              className="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await signIn();
                  setSignedIn(true);
                  setBusy(false);
                  if (cache.playlists.length === 0) await refreshPlaylists(cache);
                } catch (err) {
                  setStatus(`Sign-in failed: ${err instanceof Error ? err.message : String(err)}`);
                  setBusy(false);
                }
              }}
            >
              Sign in
            </button>
          )}
        </span>
      </header>

      {signedIn && (
        <div className="layout">
          <section className="sidebar">
            <div className="sidebar-head">
              <strong>Playlists ({visiblePlaylists.length})</strong>
              <button className="small" onClick={() => setSelected(new Set(visiblePlaylists.map((p) => p.id)))}>Select all</button>
              <button className="small" onClick={() => setSelected(new Set())}>Clear</button>
            </div>
            <div className="panel list">
              {visiblePlaylists.map((p) => {
                const tracks = cache.tracksByPlaylist[p.id];
                const stale = isStale(p.id);
                return (
                  <div
                    key={p.id}
                    className="pl-row"
                    onContextMenu={(e) =>
                      openMenu(e, [
                        { label: "Hide from sidebar", onClick: () => setPlaylistHidden(p.id, true) },
                        { label: "Open in YouTube Music", onClick: () => openPlaylist(p.id) },
                      ])
                    }
                  >
                    <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelected(p.id)} />
                    <span className="pl-title" onClick={() => toggleSelected(p.id)}>{p.title}</span>
                    {stale && <span className={`dot ${tracks ? "stale" : "none"}`} title={tracks ? `Updated ${relativeAge(cache.updatedAt[p.id])}` : "Not cached"} />}
                    {tracks && <span className="pl-meta">{tracks.length}</span>}
                    <button className="pl-hide" title="Hide from sidebar" onClick={() => setPlaylistHidden(p.id, true)}>×</button>
                  </div>
                );
              })}
              {visiblePlaylists.length === 0 && <p className="empty">All playlists hidden — use “Manage playlists”.</p>}
            </div>
            <button disabled={busy || selectedPlaylists.length === 0} onClick={() => runUpdate(selectedPlaylists)}>
              Update {selectedPlaylists.length} selected{uncachedSelected ? ` (${uncachedSelected} new)` : ""}
            </button>
            {stalePlaylists.length > 0 && (
              <button disabled={busy} onClick={() => runUpdate(stalePlaylists)}>
                Update stale ({stalePlaylists.length})
              </button>
            )}
          </section>

          <section className="songpane">
            <div className="searchbar">
              <input ref={searchRef} className="search" placeholder="Search songs…  (⌘F)" value={query} onChange={(e) => setQuery(e.currentTarget.value)} />
              {query && <button className="small" onClick={() => setQuery("")}>clear</button>}
              <label className="toggle">
                <input type="checkbox" checked={dupOnly} onChange={(e) => setDupOnly(e.currentTarget.checked)} />
                in &gt;1 playlist
              </label>
              <span className="count">{visibleSongs.length} songs</span>
            </div>

            <div className="song-head">
              <div className="col" onClick={() => sortBy("title")}>Title{arrow("title")}</div>
              <div className="col" onClick={() => sortBy("artist")}>Artist{arrow("artist")}</div>
              <div className="col" onClick={() => sortBy("count")}>In playlists{arrow("count")}</div>
            </div>
            <div className="song-scroll" ref={v.ref}>
              {visibleSongs.length === 0 ? (
                <p className="empty">
                  {songs.length === 0
                    ? "Select playlists, then “Update” to fetch their songs (cached after that)."
                    : "No songs match."}
                </p>
              ) : (
                <div className="song-inner" style={{ height: visibleSongs.length * ROW_H }}>
                  {visibleSongs.slice(v.start, v.end).map((s, idx) => {
                    const i = v.start + idx;
                    return (
                      <div
                        key={s.videoId}
                        className={`song-row${i % 2 ? " zebra" : ""}`}
                        style={{ top: i * ROW_H }}
                        onClick={() => setDetail(s)}
                        onContextMenu={(e) =>
                          openMenu(e, [
                            { label: "Open in YouTube Music", onClick: () => openSong(s.videoId) },
                            { label: "Details", onClick: () => setDetail(s) },
                          ])
                        }
                      >
                        <div className="cell title-cell">
                          {s.thumb ? <img className="thumb" src={s.thumb} loading="lazy" alt="" /> : <span className="thumb" />}
                          <span className="ttext">{s.title}</span>
                        </div>
                        <div className="cell muted">{s.artist}</div>
                        <div className="cell muted" title={s.playlists.join(", ")}>
                          {s.playlists.length === 1 ? s.playlists[0] : `${s.playlists.length} playlists`}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {showManage && (
        <Overlay title="Manage playlists" onClose={() => setShowManage(false)}>
          <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 0 }}>
            Unchecked playlists are hidden from the main sidebar (still cached). {hidden.size} hidden.
          </p>
          <input
            placeholder="Filter…"
            value={manageQuery}
            onChange={(e) => setManageQuery(e.currentTarget.value)}
            style={{ width: "100%", marginBottom: 8 }}
          />
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {manageList.map((p) => (
              <label key={p.id} className="pl-row">
                <input type="checkbox" checked={!hidden.has(p.id)} onChange={(e) => setPlaylistHidden(p.id, !e.currentTarget.checked)} />
                <span className="pl-title">{p.title}</span>
              </label>
            ))}
          </div>
        </Overlay>
      )}

      {detail && (
        <Overlay title={detail.title} onClose={() => setDetail(null)}>
          <p style={{ margin: "4px 0" }}><strong>Artist:</strong> {detail.artist || "—"}</p>
          <p style={{ margin: "4px 0", display: "flex", gap: 8, alignItems: "center" }}>
            <button className="small" onClick={() => openUrl(`https://music.youtube.com/watch?v=${detail.videoId}`)}>
              Open in YouTube Music
            </button>
            <code style={{ color: "var(--muted)" }}>{detail.videoId}</code>
          </p>
          <p style={{ margin: "10px 0 4px" }}><strong>In {detail.playlists.length} playlist(s):</strong></p>
          <ul style={{ margin: 0, paddingLeft: 18, maxHeight: "38vh", overflow: "auto" }}>
            {detail.playlists.map((name) => {
              const id = titleToId.get(name);
              return (
                <li key={name} style={{ marginBottom: 2 }}>
                  {name}
                  {id && (
                    <button
                      className="small"
                      style={{ marginLeft: 8 }}
                      onClick={() => openUrl(`https://music.youtube.com/playlist?list=${id}`)}
                    >
                      open
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </Overlay>
      )}

      {menu && (
        <div className="ctx-menu" style={{ left: menu.x, top: menu.y }} onClick={(e) => e.stopPropagation()}>
          {menu.items.map((it) => (
            <div
              key={it.label}
              className="ctx-item"
              onClick={() => {
                it.onClick();
                setMenu(null);
              }}
            >
              {it.label}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

function Overlay({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button onClick={onClose}>Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default App;
