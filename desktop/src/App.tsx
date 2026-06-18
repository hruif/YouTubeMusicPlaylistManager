import { useEffect, useMemo, useRef, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getLibraryPlaylists,
  fetchTracksForPlaylists,
  combineFromCache,
  addVideos,
  createPlaylist,
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

// Virtualization: render only the rows in view. Uses a callback ref so the scroll/resize
// listeners attach when the container actually mounts (it's gated behind sign-in, so a plain
// useEffect([]) at mount would find no element and never wire up — leaving only the first page).
function useVirtual(count: number) {
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [height, setHeight] = useState(0);
  useEffect(() => {
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(() => setHeight(el.clientHeight));
    ro.observe(el);
    setHeight(el.clientHeight);
    setScrollTop(el.scrollTop);
    return () => {
      el.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, [el]);
  const overscan = 10;
  const h = height || 600;
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - overscan);
  const end = Math.min(count, Math.ceil((scrollTop + h) / ROW_H) + overscan);
  return { ref: setEl, start, end };
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
  const [selectedSongs, setSelectedSongs] = useState<Set<string>>(new Set());
  const lastSongIndex = useRef<number | null>(null);
  const lastClick = useRef<{ id: string; t: number } | null>(null);
  const [addPicker, setAddPicker] = useState(false);
  const [addQuery, setAddQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");

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
      const { tracksByPlaylist, editableIds, failures } = await fetchTracksForPlaylists(list, 4, (done, total) =>
        setStatus(`Updating ${done}/${total}…`),
      );
      const now = Date.now();
      const updatedAt = { ...cache.updatedAt };
      for (const id of Object.keys(tracksByPlaylist)) updatedAt[id] = now;
      persist({
        ...cache,
        tracksByPlaylist: { ...cache.tracksByPlaylist, ...tracksByPlaylist },
        updatedAt,
        editable: [...new Set([...cache.editable, ...editableIds])],
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

  const editable = useMemo(() => new Set(cache.editable), [cache.editable]);
  const selectedTracks = useMemo(
    () => songs.filter((s) => selectedSongs.has(s.videoId)),
    [songs, selectedSongs],
  );
  // Targets for "Add to playlist": the shown (non-hidden) playlists; ownership can't be reliably
  // detected up front, so editable-detected ones sort first and the add attempt reports rejection.
  const addTargets = useMemo(() => {
    const q = addQuery.trim().toLowerCase();
    return visiblePlaylists
      .filter((p) => p.title.toLowerCase().includes(q))
      .sort((a, b) => Number(editable.has(b.id)) - Number(editable.has(a.id)));
  }, [visiblePlaylists, editable, addQuery]);

  // Add the selected songs to a playlist you own — optimistic, reverting on error.
  async function addSelectedTo(target: Playlist) {
    setAddPicker(false);
    const existing = cache.tracksByPlaylist[target.id] ?? [];
    const have = new Set(existing.map((t) => t.videoId));
    const toAdd = selectedTracks
      .filter((t) => !have.has(t.videoId))
      .map(({ videoId, title, artist, thumb }) => ({ videoId, title, artist, thumb }));
    if (toAdd.length === 0) {
      setStatus(`All selected songs are already in ${target.title}`);
      return;
    }
    persist({
      ...cache,
      tracksByPlaylist: { ...cache.tracksByPlaylist, [target.id]: [...existing, ...toAdd] },
    });
    setBusy(true);
    setStatus(`Adding ${toAdd.length} to ${target.title}…`);
    try {
      await addVideos(target.id, toAdd.map((t) => t.videoId));
      setStatus(`Added ${toAdd.length} to ${target.title}`);
    } catch (err) {
      persist({ ...cache, tracksByPlaylist: { ...cache.tracksByPlaylist, [target.id]: existing } });
      setStatus(`Add failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Create a new playlist from the selected songs.
  async function createFromSelection() {
    const name = newName.trim();
    if (!name) return;
    const tracks = selectedTracks.map(({ videoId, title, artist, thumb }) => ({ videoId, title, artist, thumb }));
    setCreateOpen(false);
    setNewName("");
    setBusy(true);
    setStatus(`Creating “${name}”…`);
    try {
      const newId = await createPlaylist(name, tracks.map((t) => t.videoId));
      if (newId) {
        persist({
          ...cache,
          playlists: [{ id: newId, title: name }, ...cache.playlists],
          tracksByPlaylist: { ...cache.tracksByPlaylist, [newId]: tracks },
          updatedAt: { ...cache.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cache.editable, newId])],
        });
        setStatus(`Created “${name}” with ${tracks.length} songs`);
      } else {
        setStatus(`Created “${name}” — refreshing list…`);
        await refreshPlaylists(cache);
      }
    } catch (err) {
      setStatus(`Create failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

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

  // Song selection: plain click = select one; Cmd/Ctrl+click = toggle; Shift+click = range.
  // Double-click (same row, fast) opens details — detected manually so a click after closing a
  // modal can't be mis-counted as a double-click on a different row.
  function onSongClick(e: React.MouseEvent, index: number) {
    const song = visibleSongs[index];
    const id = song.videoId;
    const prev = lastClick.current;
    if (prev && prev.id === id && e.timeStamp - prev.t < 350) {
      lastClick.current = null;
      setDetail(song);
      return;
    }
    lastClick.current = { id, t: e.timeStamp };
    if (e.shiftKey && lastSongIndex.current !== null) {
      const [a, b] = [lastSongIndex.current, index].sort((x, y) => x - y);
      const range = new Set<string>();
      for (let i = a; i <= b; i++) range.add(visibleSongs[i].videoId);
      setSelectedSongs(range);
    } else if (e.metaKey || e.ctrlKey) {
      setSelectedSongs((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      lastSongIndex.current = index;
    } else {
      setSelectedSongs(new Set([id]));
      lastSongIndex.current = index;
    }
  }

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
              <span className="count">{visibleSongs.length} songs{selectedSongs.size ? ` · ${selectedSongs.size} selected` : ""}</span>
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
                        className={`song-row${i % 2 ? " zebra" : ""}${selectedSongs.has(s.videoId) ? " selected" : ""}`}
                        style={{ top: i * ROW_H }}
                        onClick={(e) => onSongClick(e, i)}
                        onContextMenu={(e) => {
                          let count = selectedSongs.size;
                          if (!selectedSongs.has(s.videoId)) {
                            setSelectedSongs(new Set([s.videoId]));
                            lastSongIndex.current = i;
                            count = 1;
                          }
                          openMenu(e, [
                            { label: `Add ${count} to playlist…`, onClick: () => setAddPicker(true) },
                            { label: `New playlist from ${count} song${count > 1 ? "s" : ""}…`, onClick: () => setCreateOpen(true) },
                            { label: "Open in YouTube Music", onClick: () => openSong(s.videoId) },
                            { label: "Details", onClick: () => setDetail(s) },
                          ]);
                        }}
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

      {addPicker && (
        <Overlay title={`Add ${selectedTracks.length} song(s) to…`} onClose={() => setAddPicker(false)}>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Pick a playlist you own. ✓ marks ones detected as editable; others are still allowed and
            will report an error if YouTube rejects the edit.
          </p>
          <input placeholder="Filter playlists…" value={addQuery} onChange={(e) => setAddQuery(e.currentTarget.value)} style={{ width: "100%", marginBottom: 8 }} />
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {addTargets.map((p) => (
              <div key={p.id} className="pl-row" style={{ cursor: "pointer" }} onClick={() => addSelectedTo(p)}>
                {editable.has(p.id) && <span style={{ color: "var(--accent)" }}>✓</span>}
                <span className="pl-title">{p.title}</span>
                {cache.tracksByPlaylist[p.id] && <span className="pl-meta">{cache.tracksByPlaylist[p.id].length}</span>}
              </div>
            ))}
            {addTargets.length === 0 && <p className="empty">No matches.</p>}
          </div>
        </Overlay>
      )}

      {createOpen && (
        <Overlay title={`New playlist from ${selectedTracks.length} song(s)`} onClose={() => setCreateOpen(false)}>
          <input
            autoFocus
            placeholder="Playlist name"
            value={newName}
            onChange={(e) => setNewName(e.currentTarget.value)}
            onKeyDown={(e) => e.key === "Enter" && createFromSelection()}
            style={{ width: "100%", marginBottom: 10 }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={() => setCreateOpen(false)}>Cancel</button>
            <button className="primary" disabled={!newName.trim()} onClick={createFromSelection}>Create</button>
          </div>
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
