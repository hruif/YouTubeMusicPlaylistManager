import { useRef } from "react";

// How close two clicks on the same row must be to count as a double-click. Shorter than macOS's
// default, so two deliberate single clicks (e.g. select, then deselect) don't open details.
export const DOUBLE_CLICK_MS = 250;

// Returns a click handler helper: true when this click completes a double-click on the same item.
// Tracking the item id means a click after closing a dialog can't pair with a click elsewhere.
export function useDoubleClick(): (id: string) => boolean {
  const last = useRef<{ id: string; t: number } | null>(null);
  return (id) => {
    const now = performance.now();
    const prev = last.current;
    if (prev && prev.id === id && now - prev.t < DOUBLE_CLICK_MS) {
      last.current = null;
      return true;
    }
    last.current = { id, t: now };
    return false;
  };
}
