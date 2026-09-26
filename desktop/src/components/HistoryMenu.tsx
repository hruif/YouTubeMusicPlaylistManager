import { useEffect, useRef, useState } from "react";
import { HistoryIcon } from "./icons";

// One header button for Queues and Recently deleted, instead of a button each. A dot shows when
// either has something in it.
export function HistoryMenu({
  queueCount,
  deletedCount,
  disabled,
  onQueues,
  onDeleted,
}: {
  queueCount: number;
  deletedCount: number;
  disabled: boolean;
  onQueues: () => void;
  onDeleted: () => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const pending = queueCount + deletedCount > 0;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [open]);

  const choose = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <div
      className="history-menu"
      ref={rootRef}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation(); // close just this menu
          setOpen(false);
        }
      }}
    >
      <button
        className={`icon-only${pending ? " has-dot" : ""}`}
        disabled={disabled}
        aria-label={`Queues and recently deleted${pending ? " (has items)" : ""}`}
        title="Queues and recently deleted"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <HistoryIcon />
      </button>
      {open && (
        <div className="history-pop" role="menu">
          <button role="menuitem" className="history-item" onClick={choose(onQueues)}>
            <span>Queues</span>
            <span className="pl-meta">{queueCount}</span>
          </button>
          <button role="menuitem" className="history-item" onClick={choose(onDeleted)}>
            <span>Recently deleted</span>
            <span className="pl-meta">{deletedCount}</span>
          </button>
        </div>
      )}
    </div>
  );
}
