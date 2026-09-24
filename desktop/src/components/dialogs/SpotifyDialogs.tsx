import { useState } from "react";
import { fetchSpotifyPlaylist, type SpotifyTrack } from "../../lib/spotify";
import { Overlay } from "../Overlay";

const YTM_TRANSFER_HELP = "https://support.google.com/youtubemusic/answer/14729358";

export function SpotifyImportDialog({
  busy,
  onOpenUrl,
  onFail,
  onTransfer,
  onClose,
}: {
  busy: boolean;
  onOpenUrl: (url: string) => void;
  onFail: (message: string) => void;
  onTransfer: (name: string, tracks: SpotifyTrack[]) => void;
  onClose: () => void;
}) {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<{ title: string; tracks: SpotifyTrack[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState("");
  const [name, setName] = useState("");

  async function read() {
    setResult(null);
    setLoading(true);
    setProgress("Connecting to Spotify…");
    try {
      const r = await fetchSpotifyPlaylist(url, (loaded, total) => setProgress(`Loaded ${loaded}/${total || "?"}…`));
      setResult(r);
      setName(r.title);
      setProgress("");
    } catch (err) {
      setProgress("");
      onFail(`Spotify import failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Overlay title="Import a Spotify playlist" onClose={onClose}>
      <p className="dialog-hint">
        YouTube Music can also transfer playlists itself, under Settings → Privacy &amp; data → Transfer
        playlists.{" "}
        <button className="link" onClick={() => onOpenUrl(YTM_TRANSFER_HELP)}>How it works</button>
      </p>
      <div className="row-gap">
        <input
          spellCheck={false}
          autoCorrect="off"
          autoCapitalize="off"
          className="grow-input"
          aria-label="Spotify playlist link"
          placeholder="https://open.spotify.com/playlist/…"
          value={url}
          onChange={(e) => setUrl(e.currentTarget.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && url.trim() && read()}
        />
        <button className="primary" disabled={loading || !url.trim()} onClick={read}>Read</button>
      </div>
      {progress && <p className="dialog-text" role="status">{progress}</p>}
      {result && (
        <>
          <p className="dialog-text">
            <strong>{result.title}</strong> — {result.tracks.length} songs
          </p>
          <div className="panel scroll-40">
            {result.tracks.map((t, i) => (
              <div key={i} className="pl-row">
                <span className="pl-title">{t.title}</span>
                <span className="pl-meta">{t.artist}</span>
              </div>
            ))}
          </div>
          <div className="row-gap" style={{ marginTop: 10 }}>
            <input
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              className="grow-input"
              aria-label="New playlist name"
              placeholder="New playlist name"
              value={name}
              onChange={(e) => setName(e.currentTarget.value)}
            />
            <button className="primary" disabled={busy || !name.trim()} onClick={() => onTransfer(name.trim(), result.tracks)}>
              Transfer
            </button>
          </div>
          <p className="dialog-hint" style={{ marginTop: 6 }}>
            Only confident matches are added. You’ll get a list of the rest to find yourself.
          </p>
        </>
      )}
    </Overlay>
  );
}

export function TransferResultDialog({
  result,
  onSearch,
  onClose,
}: {
  result: { name: string; matched: number; unmatched: SpotifyTrack[] };
  onSearch: (t: SpotifyTrack) => void;
  onClose: () => void;
}) {
  return (
    <Overlay title="Transfer complete" onClose={onClose}>
      <p className="dialog-text">
        <strong>{result.name}</strong>: added {result.matched} song{result.matched === 1 ? "" : "s"}.
      </p>
      {result.unmatched.length > 0 ? (
        <>
          <p className="dialog-text">{result.unmatched.length} couldn’t be matched. Search for them yourself:</p>
          <SongSearchList tracks={result.unmatched} onSearch={onSearch} />
          <p className="dialog-hint" style={{ marginTop: 6 }}>
            To see this list again, right-click the playlist → “Unmatched from Spotify”.
          </p>
        </>
      ) : (
        <p className="dialog-hint">Everything matched.</p>
      )}
    </Overlay>
  );
}

function SongSearchList({ tracks, onSearch }: { tracks: SpotifyTrack[]; onSearch: (t: SpotifyTrack) => void }) {
  return (
    <div className="panel scroll-40">
      {tracks.map((t, i) => (
        <div key={i} className="pl-row">
          <span className="pl-title">{t.title}</span>
          <span className="pl-meta">{t.artist}</span>
          <button className="small" onClick={() => onSearch(t)}>Search</button>
        </div>
      ))}
    </div>
  );
}

export function UnmatchedDialog({ tracks, onSearch, onClose }: { tracks: SpotifyTrack[]; onSearch: (t: SpotifyTrack) => void; onClose: () => void }) {
  return (
    <Overlay title="Unmatched from Spotify" onClose={onClose}>
      <SongSearchList tracks={tracks} onSearch={onSearch} />
    </Overlay>
  );
}
