import type { AccountInfo, PlaylistPrivacy } from "../../lib/ytmusic";
import type { Theme } from "../../lib/settings";
import { Overlay } from "../Overlay";

export const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "⌘F", action: "Search songs" },
  { keys: "↑ / ↓", action: "Move through songs (hold ⇧ to extend the selection)" },
  { keys: "⌘A", action: "Select all songs" },
  { keys: "Return", action: "Song details" },
  { keys: "Delete", action: "Remove selected songs from a playlist" },
  { keys: "⌘Z", action: "Undo the last add or remove, while its message is showing" },
  { keys: "⌘R", action: "Refresh selected playlists" },
  { keys: "⌘,", action: "Settings" },
  { keys: "Esc", action: "Close a window, or clear the song selection" },
];

type Props = {
  currentVersion: string;
  checkingForUpdates: boolean;
  updateCheckMessage: string | null;
  canInstall: boolean;
  hasUpdate: boolean;
  installingUpdate: string | null;
  account: AccountInfo | null;
  busy: boolean;
  checkUpdates: boolean;
  replaceNames: boolean;
  autoDeleteQueues: boolean;
  autoRefreshOnLaunch: boolean;
  queuePrivacy: PlaylistPrivacy;
  theme: Theme;
  onCheckUpdates: () => void;
  onInstall: () => void;
  onDownload: () => void;
  onChange: (patch: Partial<{
    checkUpdates: boolean;
    replaceNames: boolean;
    autoDeleteQueues: boolean;
    autoRefreshOnLaunch: boolean;
    queuePrivacy: PlaylistPrivacy;
    theme: Theme;
  }>) => void;
  onSignOut: () => void;
  onOpenSource: () => void;
  onClose: () => void;
};

const PRIVACY_NOTE: Record<PlaylistPrivacy, string> = {
  PRIVATE: "Private queues open only in a browser signed into this account. Anywhere else shows a blank page.",
  PUBLIC: "Public queues open in any browser and may appear on your channel and in search.",
  UNLISTED: "Unlisted queues open in any browser from the link, but don’t appear on your channel or in search. Recommended.",
};

export function SettingsDialog(p: Props) {
  return (
    <Overlay title="Settings" onClose={p.onClose}>
      <div className="settings-section">
        <div className="settings-row">
          <div className="settings-copy">
            <strong>App version</strong>
            <span>YouTube Music Playlist Manager {p.currentVersion}</span>
          </div>
          <button disabled={p.checkingForUpdates} onClick={p.onCheckUpdates}>
            {p.checkingForUpdates ? "Checking…" : "Check for updates"}
          </button>
          {p.hasUpdate && p.canInstall && (
            <button className="small" disabled={p.installingUpdate !== null} onClick={p.onInstall}>
              {p.installingUpdate ?? "Update & restart"}
            </button>
          )}
          {p.hasUpdate && <button className="small" onClick={p.onDownload}>Download manually</button>}
        </div>
        {p.updateCheckMessage && <p className="settings-note" role="status">{p.updateCheckMessage}</p>}
        <label className="setting">
          <input type="checkbox" checked={p.checkUpdates} onChange={(e) => p.onChange({ checkUpdates: e.currentTarget.checked })} />
          Check for updates on startup
        </label>
      </div>

      <label className="setting">
        <span className="grow-input">Appearance</span>
        <select className="small" value={p.theme} onChange={(e) => p.onChange({ theme: e.currentTarget.value as Theme })}>
          <option value="system">Match system</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </label>
      <label className="setting">
        <input type="checkbox" checked={p.replaceNames} onChange={(e) => p.onChange({ replaceNames: e.currentTarget.checked })} />
        Show only custom names (hide the real titles)
      </label>
      <label className="setting">
        <input type="checkbox" checked={p.autoDeleteQueues} onChange={(e) => p.onChange({ autoDeleteQueues: e.currentTarget.checked })} />
        Delete leftover queues automatically when I quit
      </label>
      <label className="setting">
        <input type="checkbox" checked={p.autoRefreshOnLaunch} onChange={(e) => p.onChange({ autoRefreshOnLaunch: e.currentTarget.checked })} />
        Refresh the playlist list on launch
      </label>
      <label className="setting">
        <span className="grow-input">“Play in YouTube Music” queue visibility</span>
        <select className="small" value={p.queuePrivacy} onChange={(e) => p.onChange({ queuePrivacy: e.currentTarget.value as PlaylistPrivacy })}>
          <option value="UNLISTED">Unlisted</option>
          <option value="PUBLIC">Public</option>
          <option value="PRIVATE">Private</option>
        </select>
      </label>
      <p className="settings-note" style={{ marginTop: -2 }}>{PRIVACY_NOTE[p.queuePrivacy]}</p>

      <details className="shortcuts">
        <summary>Keyboard shortcuts</summary>
        <dl>
          {SHORTCUTS.map((s) => (
            <div key={s.keys} className="shortcut">
              <dt><kbd>{s.keys}</kbd></dt>
              <dd>{s.action}</dd>
            </div>
          ))}
        </dl>
      </details>

      <div className="settings-account">
        <span>
          {p.account ? (
            <>Signed in as <strong>{p.account.name}</strong>{p.account.handle ? ` · ${p.account.handle}` : ""}</>
          ) : (
            "Signed in to YouTube Music"
          )}
        </span>
        <span className="grow-input" />
        <button className="danger" disabled={p.busy} onClick={p.onSignOut}>Sign out</button>
      </div>
      <p className="settings-footer">
        YouTube Music Playlist Manager (beta)
        <button className="small" onClick={p.onOpenSource}>Source</button>
      </p>
    </Overlay>
  );
}
