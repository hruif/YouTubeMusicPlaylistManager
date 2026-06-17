import { useEffect, useState } from "react";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getAccountInfo,
  getLibraryPlaylists,
  addVideo,
  removeVideo,
} from "./lib/ytmusic";
import "./App.css";

// Phase 0 auth spike UI. Proves: embedded login (no manual headers) -> authenticated read
// (account info + library) -> authenticated write (add/remove a video). See FUTURE_DIRECTIONS.md.

function App() {
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [playlists, setPlaylists] = useState<Array<{ id: string; title: string }>>([]);
  const [playlistId, setPlaylistId] = useState("");
  const [videoId, setVideoId] = useState("");

  const append = (line: string) => setLog((prev) => [...prev, line]);

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(true);
    append(`▶ ${label}…`);
    try {
      await fn();
      append(`✓ ${label}`);
    } catch (err) {
      append(`✗ ${label}: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Auto sign-in on startup from the persisted WebView session (no window if already logged in).
  useEffect(() => {
    run("Auto sign-in (startup)", async () => {
      const names = await trySilentSignIn();
      if (names) {
        setSignedIn(true);
        append(`   restored session; cookies: ${names.join(", ")}`);
      } else {
        append("   no saved session — click Sign in");
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="container" style={{ textAlign: "left", maxWidth: 720, margin: "0 auto" }}>
      <h1>YT Music — Auth Spike</h1>
      <p style={{ opacity: 0.7 }}>
        Phase 0: prove embedded login + read + write with no manual headers.
      </p>

      <div className="row" style={{ gap: 8, flexWrap: "wrap", justifyContent: "flex-start" }}>
        <button
          disabled={busy}
          onClick={() =>
            run("Sign in", async () => {
              const names = await signIn();
              setSignedIn(true);
              append(`   cookies: ${names.join(", ")}`);
            })
          }
        >
          1. Sign in
        </button>
        <button
          disabled={busy || !signedIn}
          onClick={() => run("Read account info", async () => append(`   account: ${await getAccountInfo()}`))}
        >
          2. Read account
        </button>
        <button
          disabled={busy || !signedIn}
          onClick={() =>
            run("List library playlists", async () => {
              const pls = await getLibraryPlaylists();
              setPlaylists(pls);
              append(`   ${pls.length} playlist(s)`);
            })
          }
        >
          3. List playlists
        </button>
        <button
          disabled={busy || !signedIn}
          onClick={() =>
            run("Sign out", async () => {
              await signOut();
              setSignedIn(false);
              setPlaylists([]);
            })
          }
        >
          Sign out
        </button>
      </div>

      {playlists.length > 0 && (
        <div style={{ margin: "12px 0" }}>
          <strong>Pick a playlist you own (sets the ID below):</strong>
          <ul style={{ maxHeight: 160, overflow: "auto" }}>
            {playlists.map((p) => (
              <li key={p.id}>
                <button style={{ padding: "2px 6px" }} onClick={() => setPlaylistId(p.id)}>
                  use
                </button>{" "}
                {p.title} <code style={{ opacity: 0.6 }}>{p.id}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="row" style={{ gap: 8, flexWrap: "wrap", justifyContent: "flex-start" }}>
        <input
          placeholder="playlist id (one you own)"
          value={playlistId}
          onChange={(e) => setPlaylistId(e.currentTarget.value)}
          style={{ minWidth: 240 }}
        />
        <input
          placeholder="video id (e.g. dQw4w9WgXcQ)"
          value={videoId}
          onChange={(e) => setVideoId(e.currentTarget.value)}
          style={{ minWidth: 200 }}
        />
        <button
          disabled={busy || !signedIn || !playlistId || !videoId}
          onClick={() => run("WRITE: add video", () => addVideo(playlistId, videoId))}
        >
          4. Add video (WRITE)
        </button>
        <button
          disabled={busy || !signedIn || !playlistId || !videoId}
          onClick={() => run("WRITE: remove video", () => removeVideo(playlistId, videoId))}
        >
          Remove video (cleanup)
        </button>
      </div>

      <pre
        style={{
          marginTop: 16,
          padding: 12,
          background: "rgba(0,0,0,0.06)",
          borderRadius: 8,
          minHeight: 160,
          whiteSpace: "pre-wrap",
          fontSize: 13,
        }}
      >
        {log.join("\n") || "Log output appears here."}
      </pre>
    </main>
  );
}

export default App;
