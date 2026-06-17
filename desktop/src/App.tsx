import { useEffect, useMemo, useRef, useState } from "react";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getLibraryPlaylists,
  getCombinedSongs,
  type CombinedSong,
} from "./lib/ytmusic";
import "./App.css";

// Phase 1: read-only parity. Auth (Phase 0) is proven; this builds the combined song view —
// select playlists, merge their songs, and see which playlists each song appears in.

type Playlist = { id: string; title: string };
type SortKey = "title" | "artist" | "count";

function App() {
  const [status, setStatus] = useState("Starting…");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [songs, setSongs] = useState<CombinedSong[]>([]);
  const [sortKey, setSortKey] = useState<SortKey>("title");
  const [sortAsc, setSortAsc] = useState(true);

  async function loadPlaylists() {
    setBusy(true);
    setStatus("Loading playlists…");
    try {
      const pls = await getLibraryPlaylists();
      setPlaylists(pls);
      setStatus(`${pls.length} playlists`);
    } catch (err) {
      setStatus(`Failed to load playlists: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Auto sign-in on startup from the persisted WebView session, then load playlists.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return; // guard React StrictMode's double-invoke in dev
    started.current = true;
    (async () => {
      setBusy(true);
      setStatus("Signing in…");
      try {
        const names = await trySilentSignIn();
        if (names) {
          setSignedIn(true);
          setBusy(false);
          await loadPlaylists();
        } else {
          setStatus("Not signed in");
          setBusy(false);
        }
      } catch (err) {
        setStatus(`Sign-in failed: ${err instanceof Error ? err.message : String(err)}`);
        setBusy(false);
      }
    })();
  }, []);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function loadSongs() {
    const chosen = playlists.filter((p) => selected.has(p.id));
    if (chosen.length === 0) return;
    setBusy(true);
    setStatus(`Loading songs from ${chosen.length} playlist(s)…`);
    try {
      const combined = await getCombinedSongs(chosen);
      setSongs(combined);
      setStatus(`${combined.length} unique songs across ${chosen.length} playlist(s)`);
    } catch (err) {
      setStatus(`Failed to load songs: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

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

  function header(key: SortKey, label: string) {
    const arrow = sortKey === key ? (sortAsc ? " ▲" : " ▼") : "";
    return (
      <th
        style={{ textAlign: "left", cursor: "pointer", padding: "6px 10px", userSelect: "none" }}
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
    <main style={{ maxWidth: 1000, margin: "0 auto", padding: 16, textAlign: "left" }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ margin: 0 }}>YouTube Music — Library</h1>
        <span style={{ opacity: 0.6, fontSize: 13 }}>{status}</span>
        <span style={{ marginLeft: "auto" }}>
          {signedIn ? (
            <button
              disabled={busy}
              onClick={async () => {
                await signOut();
                setSignedIn(false);
                setPlaylists([]);
                setSelected(new Set());
                setSongs([]);
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
                  await loadPlaylists();
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
        <div style={{ display: "flex", gap: 16, marginTop: 16, alignItems: "flex-start" }}>
          {/* Playlist selector */}
          <section style={{ flex: "0 0 280px" }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
              <strong style={{ flex: 1 }}>Playlists ({playlists.length})</strong>
              <button style={{ padding: "1px 6px" }} onClick={() => setSelected(new Set(playlists.map((p) => p.id)))}>
                all
              </button>
              <button style={{ padding: "1px 6px" }} onClick={() => setSelected(new Set())}>
                none
              </button>
            </div>
            <div style={{ maxHeight: 420, overflow: "auto", border: "1px solid rgba(0,0,0,0.15)", borderRadius: 6 }}>
              {playlists.map((p) => (
                <label key={p.id} style={{ display: "flex", gap: 6, padding: "3px 8px", alignItems: "center" }}>
                  <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)} />
                  <span style={{ fontSize: 13 }}>{p.title}</span>
                </label>
              ))}
            </div>
            <button disabled={busy || selected.size === 0} style={{ marginTop: 8, width: "100%" }} onClick={loadSongs}>
              Load songs from {selected.size} selected
            </button>
          </section>

          {/* Combined song table */}
          <section style={{ flex: 1, minWidth: 0 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid rgba(0,0,0,0.2)" }}>
                  {header("title", "Title")}
                  {header("artist", "Artist")}
                  {header("count", "In playlists")}
                </tr>
              </thead>
              <tbody>
                {sortedSongs.map((s) => (
                  <tr key={s.videoId} style={{ borderBottom: "1px solid rgba(0,0,0,0.08)" }}>
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
                      Select playlists and click “Load songs”.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </main>
  );
}

export default App;
