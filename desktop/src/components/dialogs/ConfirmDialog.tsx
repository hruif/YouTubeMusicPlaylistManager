import { Overlay } from "../Overlay";

export type ConfirmState = { title: string; body: string; onConfirm: () => void };

export function ConfirmDialog({ confirm, onClose }: { confirm: ConfirmState; onClose: () => void }) {
  return (
    <Overlay title={confirm.title} onClose={onClose}>
      <p className="dialog-text pre-line">{confirm.body}</p>
      <div className="dialog-actions">
        {/* Cancel is autofocused so Enter (and Esc) cancel — Enter never fires a destructive
            confirm that has no other safeguard. */}
        <button autoFocus onClick={onClose}>Cancel</button>
        <button
          className="primary"
          onClick={() => {
            onClose();
            confirm.onConfirm();
          }}
        >
          Confirm
        </button>
      </div>
    </Overlay>
  );
}

export function ErrorDialog({ message, onClose }: { message: string; onClose: () => void }) {
  return (
    <Overlay title="Something went wrong" onClose={onClose}>
      <p className="dialog-text break" role="alert">{message}</p>
      <div className="dialog-actions">
        <button className="primary" autoFocus onClick={onClose}>OK</button>
      </div>
    </Overlay>
  );
}

export function ExitDialog({
  queueCount,
  onCancel,
  onKeep,
  onDelete,
}: {
  queueCount: number;
  onCancel: () => void;
  onKeep: () => void;
  onDelete: () => void;
}) {
  return (
    <Overlay title="Leftover queues" onClose={onCancel}>
      <p className="dialog-text">
        You have {queueCount} temporary “Play in YouTube Music” queue{queueCount === 1 ? "" : "s"} on your account.
        Delete {queueCount === 1 ? "it" : "them"} before closing?
      </p>
      <div className="dialog-actions">
        <button onClick={onCancel}>Cancel</button>
        <button onClick={onKeep}>Keep &amp; close</button>
        <button className="danger" onClick={onDelete}>Delete &amp; close</button>
      </div>
    </Overlay>
  );
}
