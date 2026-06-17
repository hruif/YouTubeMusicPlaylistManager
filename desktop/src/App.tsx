import { useEffect, useMemo, useRef, useState } from "react";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getLibraryPlaylists,
  fetchTracksForPlaylists,
  combineFromCache,
  type CombinedSong,
} from "./lib/ytmusic";
import { loadCache, saveCache, EMPTY_CACHE, type LibraryCache } from "./lib/cache";
import "./App.css";

// Phase 1: read-only parity, cache-driven. Library cached locally (text) for instant browsing;
// network only on explicit "Update". Hide unwanted playlists; search + sort + per-song details.

type SortKey = "title" | "artist" | "count";

function App() {
  const [status, setStatus] = useState("Starting…");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [cache, setCache] = useState<LibraryCache>({ ...EMPTY_CACHE });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>("title");
  const [sortAsc, setSortAsc] = useState(true);
  const [query, setQuery] = useState("");
  const [showManage, setShowManage] = useState(false);
  const [manageQuery, setManageQuery] = useState("");
  const [detail, setDetail] = useState<CombinedSong | null>(null);

  function persist(next: LibraryCache) {
    setCache(next);
    void saveCache(next);
  }

  async function refreshPlaylists(current: LibraryCache) {
    setBusy(true);
    setStatus("Refreshing playlist list…");
    try {
      const playlists = await getLibraryPlaylists();
      const next = { ...current, playlists };
      persist(next);
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

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function setHidden(id: string, hide: boolean) {
    const next = new Set(cache.hidden);
    if (hide) next.add(id);
    else next.delete(id);
    persist({ ...cache, hidden: [...next] });
    if (hide) setSelected((prev) => {
      const s = new Set(prev);
      s.delete(id);
      return s;
    });
  }

  const selectedPlaylists = useMemo(
    () => cache.playlists.filter((p) => selected.has(p.id)),
    [cache.playlists, selected],
  );

  async function updateSelected() {
    if (selectedPlaylists.length === 0) return;
    setBusy(true);
    setStatus(`Updating 0/${selectedPlaylists.length}…`);
    try {
      const { tracksByPlaylist, failures } = await fetchTracksForPlaylists(
        selectedPlaylists,
        4,
        (done, total) => setStatus(`Updating ${done}/${total}…`),
      );
      const now = Date.now();
      const updatedAt = { ...cache.updatedAt };
      for (const id of Object.keys(tracksByPlaylist)) updatedAt[id] = now;
      persist({
        ...cache,
        tracksByPlaylist: { ...cache.tracksByPlaylist, ...tracksByPlaylist },
        updatedAt,
      });
      setStatus(
        failures.length
          ? `Updated ${Object.keys(tracksByPlaylist).length}; ${failures.length} failed (retry)`
          : `Updated ${Object.keys(tracksByPlaylist).length} playlist(s)`,
      );
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
    const filtered = q
      ? songs.filter((s) => s.title.toLowerCase().includes(q) || s.artist.toLowerCase().includes(q))
      : songs;
    const copy = [...filtered];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "title") cmp = a.title.localeCompare(b.title);
      else if (sortKey === "artist") cmp = a.artist.localeCompare(b.artist);
      else cmp = a.playlists.length - b.playlists.length;
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [songs, query, sortKey, sortAsc]);

  const uncachedSelected = selectedPlaylists.filter((p) => !cache.tracksByPlaylist[p.id]).length;

  function header(key: SortKey, label: string) {
    const arrow = sortKey === key ? (sortAsc ? " ▲" : " ▼") : "";
    return (
      <th
        style={{ textAlign: "left", cursor: "pointer", padding: "6px 10px", userSelect: "none", position: "sticky", top: 0, background: "var(--app-bg,#fff)", overflow: "hidden", textOverflow: "ellipsis" }}
        onClick={() => {
          if (sortKey === key) setSortAsc((v) => !v);
          else {
            setSortKey(key);
            setSortAsc(true);
          }
        }}
      >
        {label}
        {arrow}
      </th>
    );
  }

  const cell: React.CSSProperties = {
    padding: "4px 10px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const manageList = cache.playlists.filter((p) =>
    p.title.toLowerCase().includes(manageQuery.trim().toLowerCase()),
  );

  return (
    <main style={{ height: "100vh", display: "flex", flexDirection: "column", padding: 16, boxSizing: "border-box", textAlign: "left", overflow: "hidden" }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12, flex: "0 0 auto" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>YouTube Music — Library</h1>
        <span style={{ opacity: 0.6, fontSize: 13 }}>{status}</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
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
        <div style={{ display: "flex", gap: 16, marginTop: 16, flex: "1 1 auto", minHeight: 0 }}>
          {/* Playlist selector (visible playlists only) */}
          <section style={{ flex: "0 0 280px", display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center" }}>
              <strong style={{ flex: 1 }}>Playlists ({visiblePlaylists.length})</strong>
              <button style={{ padding: "1px 6px" }} onClick={() => setSelected(new Set(visiblePlaylists.map((p) => p.id)))}>all</button>
              <button style={{ padding: "1px 6px" }} onClick={() => setSelected(new Set())}>none</button>
            </div>
            <div style={{ flex: "1 1 auto", overflow: "auto", border: "1px solid rgba(128,128,128,0.3)", borderRadius: 6 }}>
              {visiblePlaylists.map((p) => (
                <label key={p.id} style={{ display: "flex", gap: 6, padding: "3px 8px", alignItems: "center" }}>
                  <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelected(p.id)} />
                  <span style={{ fontSize: 13, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.title}</span>
                  {cache.tracksByPlaylist[p.id] && <span style={{ fontSize: 11, opacity: 0.5 }}>{cache.tracksByPlaylist[p.id].length}</span>}
                </label>
              ))}
              {visiblePlaylists.length === 0 && (
                <p style={{ padding: 10, opacity: 0.6, fontSize: 13 }}>All playlists hidden — use “Manage playlists”.</p>
              )}
            </div>
            <button disabled={busy || selectedPlaylists.length === 0} style={{ marginTop: 8 }} onClick={updateSelected}>
              Update {selectedPlaylists.length} selected{uncachedSelected ? ` (${uncachedSelected} not cached)` : ""}
            </button>
          </section>

          {/* Combined song table */}
          <section style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ display: "flex", gap: 10, marginBottom: 6, alignItems: "center" }}>
              <input
                placeholder="Search songs…"
                value={query}
                onChange={(e) => setQuery(e.currentTarget.value)}
                style={{ flex: 1, padding: "4px 8px" }}
              />
              <span style={{ fontSize: 13, opacity: 0.7 }}>{visibleSongs.length} songs</span>
            </div>
            <div style={{ flex: "1 1 auto", overflow: "auto", border: "1px solid rgba(128,128,128,0.3)", borderRadius: 6 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, tableLayout: "fixed" }}>
                <colgroup>
                  <col style={{ width: "45%" }} />
                  <col style={{ width: "33%" }} />
                  <col style={{ width: "22%" }} />
                </colgroup>
                <thead>
                  <tr>
                    {header("title", "Title")}
                    {header("artist", "Artist")}
                    {header("count", "In playlists")}
                  </tr>
                </thead>
                <tbody>
                  {visibleSongs.map((s) => (
                    <tr
                      key={s.videoId}
                      style={{ borderTop: "1px solid rgba(128,128,128,0.15)", cursor: "pointer" }}
                      onClick={() => setDetail(s)}
                    >
                      <td style={cell}>{s.title}</td>
                      <td style={{ ...cell, opacity: 0.8 }}>{s.artist}</td>
                      <td style={{ ...cell, opacity: 0.8 }} title={s.playlists.join(", ")}>
                        {s.playlists.length === 1 ? s.playlists[0] : `${s.playlists.length} playlists`}
                      </td>
                    </tr>
                  ))}
                  {visibleSongs.length === 0 && (
                    <tr>
                      <td colSpan={3} style={{ padding: 16, opacity: 0.6 }}>
                        {songs.length === 0
                          ? "Select playlists, then “Update” to fetch their songs (cached after that)."
                          : "No songs match your search."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      {/* Manage-playlists modal: every playlist, show/hide toggles */}
      {showManage && (
        <Overlay onClose={() => setShowManage(false)} title="Manage playlists">
          <p style={{ fontSize: 13, opacity: 0.7, marginTop: 0 }}>
            Unchecked playlists are hidden from the main sidebar (still cached). {hidden.size} hidden.
          </p>
          <input
            placeholder="Filter…"
            value={manageQuery}
            onChange={(e) => setManageQuery(e.currentTarget.value)}
            style={{ width: "100%", padding: "4px 8px", marginBottom: 8, boxSizing: "border-box" }}
          />
          <div style={{ maxHeight: "50vh", overflow: "auto", border: "1px solid rgba(128,128,128,0.3)", borderRadius: 6 }}>
            {manageList.map((p) => (
              <label key={p.id} style={{ display: "flex", gap: 8, padding: "4px 8px", alignItems: "center" }}>
                <input type="checkbox" checked={!hidden.has(p.id)} onChange={(e) => setHidden(p.id, !e.currentTarget.checked)} />
                <span style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.title}</span>
              </label>
            ))}
          </div>
        </Overlay>
      )}

      {/* Song details */}
      {detail && (
        <Overlay onClose={() => setDetail(null)} title={detail.title}>
          <div style={{ fontSize: 14 }}>
            <p style={{ margin: "4px 0" }}><strong>Artist:</strong> {detail.artist || "—"}</p>
            <p style={{ margin: "4px 0" }}><strong>Video ID:</strong> <code>{detail.videoId}</code></p>
            <p style={{ margin: "8px 0 4px" }}><strong>In {detail.playlists.length} playlist(s):</strong></p>
            <ul style={{ margin: 0, paddingLeft: 18, maxHeight: "40vh", overflow: "auto" }}>
              {detail.playlists.map((name) => <li key={name}>{name}</li>)}
            </ul>
          </div>
        </Overlay>
      )}
    </main>
  );
}

function Overlay({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10 }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: "var(--app-bg,#fff)", color: "inherit", borderRadius: 10, padding: 16, width: 460, maxWidth: "90vw", boxShadow: "0 10px 40px rgba(0,0,0,0.3)" }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8 }}>
          <h2 style={{ margin: 0, fontSize: 18, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</h2>
          <button onClick={onClose}>Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default App;
