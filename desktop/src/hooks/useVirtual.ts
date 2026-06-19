import { useEffect, useState } from "react";
import { ROW_H } from "../lib/format";

// Virtualization: render only the rows in view. Uses a callback ref so the scroll/resize listeners
// attach when the container actually mounts (it's gated behind sign-in, so a plain useEffect([]) at
// mount would find no element and never wire up — leaving only the first page).
export function useVirtual(count: number) {
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [height, setHeight] = useState(0);
  useEffect(() => {
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(() => setHeight(el.clientHeight));
    ro.observe(el);
    setHeight(el.clientHeight);
    setScrollTop(el.scrollTop);
    return () => {
      el.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, [el]);
  const overscan = 10;
  const h = height || 600;
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - overscan);
  const end = Math.min(count, Math.ceil((scrollTop + h) / ROW_H) + overscan);
  return { ref: setEl, start, end };
}
