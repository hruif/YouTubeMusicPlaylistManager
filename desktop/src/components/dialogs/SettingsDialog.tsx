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

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "Match system" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

// A tiny window drawing in each theme's colors; "Match system" is split light/dark.
function ThemePreview({ theme }: { theme: Theme }) {
  const light = { bg: "#faf6f6", panel: "#ffffff", line: "#d9cfd1" };
  const dark = { bg: "#1b1718", panel: "#2c2627", line: "#4a4143" };
  const drawWindow = (c: typeof light, clip?: string) => (
    <g clipPath={clip}>
      <rect x="0" y="0" width="64" height="42" rx="6" fill={c.bg} />
      <rect x="5" y="9" width="16" height="28" rx="2" fill={c.panel} />
      <rect x="24" y="9" width="35" height="28" rx="2" fill={c.panel} />
      <rect x="27" y="14" width="22" height="3" rx="1.5" fill={c.line} />
      <rect x="27" y="20" width="28" height="3" rx="1.5" fill={c.line} />
      <rect x="27" y="26" width="16" height="3" rx="1.5" fill={c.line} />
      <circle cx="8" cy="5" r="1.4" fill="#ff5f7a" />
    </g>
  );
  return (
    <svg className="theme-preview" viewBox="0 0 64 42" aria-hidden="true">
      <defs>
        <clipPath id="half-dark">
          <polygon points="64,0 64,42 0,42" />
        </clipPath>
      </defs>
      {theme === "dark" ? drawWindow(dark) : drawWindow(light)}
      {theme === "system" && drawWindow(dark, "url(#half-dark)")}
    </svg>
  );
}

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

      <div className="setting setting-stack">
        <span id="appearance-label">Appearance</span>
        <div className="theme-picker" role="radiogroup" aria-labelledby="appearance-label">
          {THEMES.map((t) => (
            <label key={t.value} className={`theme-option${p.theme === t.value ? " on" : ""}`}>
              <input
                type="radio"
                name="theme"
                className="visually-hidden"
                checked={p.theme === t.value}
                onChange={() => p.onChange({ theme: t.value })}
              />
              <ThemePreview theme={t.value} />
              <span>{t.label}</span>
            </label>
          ))}
        </div>
      </div>
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
