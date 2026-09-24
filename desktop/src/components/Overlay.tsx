import { useEffect, useId, useRef } from "react";

const FOCUSABLE = 'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Overlay({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const titleId = useId();
  const modalRef = useRef<HTMLDivElement>(null);

  // Move focus into the dialog on open (unless a child already took it via autoFocus), and hand it
  // back to whatever had it when the dialog closes.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const modal = modalRef.current;
    if (modal && !modal.contains(document.activeElement)) {
      const body = modal.querySelector(".modal-body")?.querySelector<HTMLElement>(FOCUSABLE);
      (body ?? modal.querySelector<HTMLElement>(FOCUSABLE))?.focus();
    }
    return () => previous?.focus?.();
  }, []);

  // Keep Tab cycling inside the dialog.
  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key !== "Tab" || !modalRef.current) return;
    const items = [...modalRef.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    // The backdrop swallows clicks but doesn't close the dialog: only Close or Esc do. Closing on an
    // outside click let a burst of clicks close the dialog and land on the row beneath, which then
    // reopened it on the next double-click.
    <div className="overlay">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={modalRef} onKeyDown={onKeyDown}>
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button onClick={onClose}>Close</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
