import type { ReactNode } from "react";
import type { Playlist, Track } from "../../lib/ytmusic";
import { relativeAge } from "../../lib/format";
import { Overlay } from "../Overlay";

function InfoSection({ title }: { title: string }) {
  return <div className="info-section">{title}</div>;
}

function InfoRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="info-row">
      <div className="info-label">{label}</div>
      <div className="info-value">{children}</div>
    </div>
  );
}

function timestampLabel(timestamp: number | undefined): string {
  if (!timestamp) return "Never";
  return `${new Date(timestamp).toLocaleString()} (${relativeAge(timestamp)})`;
}

export function PlaylistInfoDialog({
  playlist: p,
  tracks,
  updatedAt,
  removedCount,
  unmatchedCount,
  owned,
  external,
  inSidebar,
  queueCreatedAt,
  busy,
  onOpen,
  onExport,
  onToggleSidebar,
  onRemoveRepeats,
  onShowRemoved,
  onShowUnmatched,
  onClose,
}: {
  playlist: Playlist;
  tracks: Track[] | undefined; // undefined = not loaded
  updatedAt: number | undefined;
  removedCount: number;
  unmatchedCount: number;
  owned: boolean;
  external: boolean;
  inSidebar: boolean;
  queueCreatedAt: number | undefined;
  busy: boolean;
  onOpen: () => void;
  onExport: () => void;
  onToggleSidebar: () => void;
  onRemoveRepeats: () => void;
  onShowRemoved: () => void;
  onShowUnmatched: () => void;
  onClose: () => void;
}) {
  const ownedText = owned ? "Yes" : external || tracks ? "No" : "Unknown";
  return (
    <Overlay title={p.title} onClose={onClose}>
      <div className="info-actions">
        <button className="small" onClick={onOpen}>Open in YouTube Music</button>
        <button className="small" onClick={onExport}>Export CSV</button>
        <button className="small" onClick={onToggleSidebar}>{inSidebar ? "Remove from sidebar" : "Show in sidebar"}</button>
        {owned && (
          <button className="small" disabled={busy || !tracks} onClick={onRemoveRepeats}>Remove repeats</button>
        )}
        {removedCount > 0 && <button className="small" onClick={onShowRemoved}>Removed songs</button>}
        {unmatchedCount > 0 && <button className="small" onClick={onShowUnmatched}>Unmatched</button>}
      </div>
      <div className="scroll-62">
        <InfoSection title="General" />
        <InfoRow label="Source">{external ? "Added by link" : "Your library"}</InfoRow>
        <InfoRow label="Owned by you">{ownedText}</InfoRow>
        {queueCreatedAt && <InfoRow label="Temporary queue">Created {timestampLabel(queueCreatedAt)}</InfoRow>}
        <InfoRow label="Playlist ID"><code>{p.id}</code></InfoRow>

        <InfoSection title="Songs" />
        <InfoRow label="Songs">{tracks ? tracks.length : "Not loaded"}</InfoRow>
        {tracks && <InfoRow label="Unique songs">{new Set(tracks.map((t) => t.videoId)).size}</InfoRow>}
        <InfoRow label="Last refreshed">{timestampLabel(updatedAt)}</InfoRow>
        {removedCount > 0 && <InfoRow label="Removed songs">{removedCount}</InfoRow>}
        {unmatchedCount > 0 && <InfoRow label="Unmatched songs">{unmatchedCount}</InfoRow>}
      </div>
    </Overlay>
  );
}
