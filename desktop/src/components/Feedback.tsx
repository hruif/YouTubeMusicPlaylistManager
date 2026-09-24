import { useEffect, useRef } from "react";

export type Progress = { label: string; done?: number; total?: number };
export type ToastAction = { label: string; run: () => void };
export type Toast = { id: number; message: string; action?: ToastAction };

// The header's status slot: an error (until dismissed or the next action starts), else what's
// running now, else nothing.
export function StatusArea({
  progress,
  error,
  onRetry,
  onDetails,
  onDismiss,
}: {
  progress: Progress | null;
  error: { message: string; retry?: () => void } | null;
  onRetry: () => void;
  onDetails: () => void;
  onDismiss: () => void;
}) {
  if (error) {
    return (
      <span className="status status-error" role="alert">
        <button className="status-msg" title={`${error.message}\n\nClick for the full message.`} onClick={onDetails}>
          <span aria-hidden="true">⚠ </span>
          {error.message}
        </button>
        {error.retry && <button className="small" onClick={onRetry}>Retry</button>}
        <button className="status-x" aria-label="Dismiss error" onClick={onDismiss}>✕</button>
      </span>
    );
  }
  if (!progress) return <span className="status" role="status" />;
  const known = progress.total !== undefined && progress.total > 0;
  return (
    <span className="status" role="status">
      <span className="status-msg">
        {progress.label}
        {known ? ` ${progress.done ?? 0}/${progress.total}` : "…"}
      </span>
      {known ? (
        <span className="progress-bar" aria-hidden="true">
          <i style={{ width: `${Math.round(((progress.done ?? 0) / progress.total!) * 100)}%` }} />
        </span>
      ) : (
        <span className="spinner" aria-hidden="true" />
      )}
    </span>
  );
}

const TOAST_MS = 4000;
const TOAST_ACTION_MS = 8000; // longer when there's something to click (e.g. Undo)

function ToastItem({ toast, onExpire }: { toast: Toast; onExpire: (id: number) => void }) {
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const start = () => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onExpire(toast.id), toast.action ? TOAST_ACTION_MS : TOAST_MS);
  };
  useEffect(() => {
    start();
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    // Hovering pauses the timer, so a toast doesn't vanish while you're reaching for its button.
    <div className="toast" onMouseEnter={() => clearTimeout(timer.current)} onMouseLeave={start}>
      <span>{toast.message}</span>
      {toast.action && (
        <button
          className="link"
          onClick={() => {
            toast.action!.run();
            onExpire(toast.id);
          }}
        >
          {toast.action.label}
        </button>
      )}
    </div>
  );
}

export function Toasts({ toasts, onExpire }: { toasts: Toast[]; onExpire: (id: number) => void }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onExpire={onExpire} />
      ))}
    </div>
  );
}
