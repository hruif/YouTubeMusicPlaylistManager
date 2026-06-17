import { useEffect, useMemo, useRef, useState } from "react";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getLibraryPlaylists,
  fetchTracksForPlaylists,
  combineFromCache,
} from "./lib/ytmusic";
import { loadCache, saveCache, EMPTY_CACHE, type LibraryCache } from "./lib/cache";
import "./App.css";

// Phase 1: read-only parity, cache-driven. The library is cached locally (text), so browsing is
// instant; we hit the network only on an explicit "Update". See dev-docs/FUTURE_DIRECTIONS.md.

type SortKey = "title" | "artist" | "count";

function App() {
  const [status, setStatus] = useState("Starting…");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [cache, setCache] = useState<LibraryCache>({ ...EMPTY_CACHE });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>("title");
  const [sortAsc, setSortAsc] = useState(true);

  async function refreshPlaylists(current: LibraryCache) {
    setBusy(true);
    setStatus("Refreshing playlist list…");
    try {
      const playlists = await getLibraryPlaylists();
      const next = { ...current, playlists };
      setCache(next);
      await saveCache(next);
      setStatus(`${playlists.length} playlists`);
    } catch (err) {
      setStatus(`Failed to refresh playlists: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Startup: silent sign-in + load cache (instant). Fetch the playlist list only if we have none.
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

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const selectedPlaylists = useMemo(
    () => cache.playlists.filter((p) => selected.has(p.id)),
    [cache.playlists, selected],
  );

  // Update tracks for the selected playlists (network), then persist — the only slow path.
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
      const next: LibraryCache = {
        ...cache,
        tracksByPlaylist: { ...cache.tracksByPlaylist, ...tracksByPlaylist },
        updatedAt,
      };
      setCache(next);
      await saveCache(next);
      setStatus(
        failures.length
          ? `Updated ${Object.keys(tracksByPlaylist).length}; ${failures.length} failed (retry the update)`
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

  const sortedSongs = useMemo(() => {
    const copy = [...songs];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "title") cmp = a.title.localeCompare(b.title);
      else if (sortKey === "artist") cmp = a.artist.localeCompare(b.artist);
      else cmp = a.playlists.length - b.playlists.length;
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [songs, sortKey, sortAsc]);

  // How many selected playlists have no cached tracks yet.
  const uncachedSelected = selectedPlaylists.filter((p) => !cache.tracksByPlaylist[p.id]).length;

  function header(key: SortKey, label: string) {
    const arrow = sortKey === key ? (sortAsc ? " ▲" : " ▼") : "";
    return (
      <th
        style={{ textAlign: "left", cursor: "pointer", padding: "6px 10px", userSelect: "none", position: "sticky", top: 0, background: "var(--app-bg, #fff)" }}
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

  return (
    <main style={{ height: "100vh", display: "flex", flexDirection: "column", padding: 16, boxSizing: "border-box", textAlign: "left", overflow: "hidden" }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12, flex: "0 0 auto" }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>YouTube Music — Library</h1>
        <span style={{ opacity: 0.6, fontSize: 13 }}>{status}</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {signedIn && (
            <button disabled={busy} onClick={() => refreshPlaylists(cache)}>
              Refresh playlist list
            </button>
          )}
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
          {/* Playlist selector */}
          <section style={{ flex: "0 0 280px", display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center" }}>
              <strong style={{ flex: 1 }}>Playlists ({cache.playlists.length})</strong>
              <button style={{ padding: "1px 6px" }} onClick={() => setSelected(new Set(cache.playlists.map((p) => p.id)))}>
                all
              </button>
              <button style={{ padding: "1px 6px" }} onClick={() => setSelected(new Set())}>
                none
              </button>
            </div>
            <div style={{ flex: "1 1 auto", overflow: "auto", border: "1px solid rgba(128,128,128,0.3)", borderRadius: 6 }}>
              {cache.playlists.map((p) => (
                <label key={p.id} style={{ display: "flex", gap: 6, padding: "3px 8px", alignItems: "center" }}>
                  <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)} />
                  <span style={{ fontSize: 13, flex: 1 }}>{p.title}</span>
                  {cache.tracksByPlaylist[p.id] && (
                    <span style={{ fontSize: 11, opacity: 0.5 }}>{cache.tracksByPlaylist[p.id].length}</span>
                  )}
                </label>
              ))}
            </div>
            <button disabled={busy || selectedPlaylists.length === 0} style={{ marginTop: 8 }} onClick={updateSelected}>
              Update {selectedPlaylists.length} selected{uncachedSelected ? ` (${uncachedSelected} not cached)` : ""}
            </button>
          </section>

          {/* Combined song table */}
          <section style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <div style={{ marginBottom: 4, fontSize: 13, opacity: 0.7 }}>{songs.length} songs</div>
            <div style={{ flex: "1 1 auto", overflow: "auto", border: "1px solid rgba(128,128,128,0.3)", borderRadius: 6 }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    {header("title", "Title")}
                    {header("artist", "Artist")}
                    {header("count", "In playlists")}
                  </tr>
                </thead>
                <tbody>
                  {sortedSongs.map((s) => (
                    <tr key={s.videoId} style={{ borderTop: "1px solid rgba(128,128,128,0.15)" }}>
                      <td style={{ padding: "4px 10px" }}>{s.title}</td>
                      <td style={{ padding: "4px 10px", opacity: 0.8 }}>{s.artist}</td>
                      <td style={{ padding: "4px 10px", opacity: 0.8 }} title={s.playlists.join(", ")}>
                        {s.playlists.length === 1 ? s.playlists[0] : `${s.playlists.length} playlists`}
                      </td>
                    </tr>
                  ))}
                  {sortedSongs.length === 0 && (
                    <tr>
                      <td colSpan={3} style={{ padding: 16, opacity: 0.6 }}>
                        Select playlists, then “Update” to fetch their songs (cached after that).
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

export default App;
