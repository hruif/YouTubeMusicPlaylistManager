import { useEffect, useState } from "react";

// How long the pointer rests on an element before its tip shows. The browser's own tooltips (the
// `title` attribute) wait about a second, which is too slow for scanning a list.
export const TIP_DELAY_MS = 250;

// One shared tooltip for any element with a `data-tip` attribute. Drawn at the top level (not
// inside the element), so rows that clip their contents don't cut it off.
export function HoverTip() {
  const [tip, setTip] = useState<{ text: string; x: number; y: number } | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let current: HTMLElement | null = null;
    const hide = () => {
      clearTimeout(timer);
      current = null;
      setTip(null);
    };
    const onOver = (e: MouseEvent) => {
      const el = (e.target as Element | null)?.closest?.<HTMLElement>("[data-tip]") ?? null;
      if (el === current) return;
      hide();
      if (!el?.dataset.tip) return;
      current = el;
      timer = setTimeout(() => {
        const r = el.getBoundingClientRect();
        setTip({ text: el.dataset.tip!, x: r.left, y: r.bottom + 6 });
      }, TIP_DELAY_MS);
    };
    document.addEventListener("mouseover", onOver);
    document.addEventListener("mousedown", hide);
    document.addEventListener("scroll", hide, true);
    window.addEventListener("blur", hide);
    return () => {
      hide();
      document.removeEventListener("mouseover", onOver);
      document.removeEventListener("mousedown", hide);
      document.removeEventListener("scroll", hide, true);
      window.removeEventListener("blur", hide);
    };
  }, []);

  if (!tip) return null;
  return (
    <div className="hover-tip" role="tooltip" style={{ left: tip.x, top: tip.y, maxWidth: `calc(100vw - ${tip.x}px - 12px)` }}>
      {tip.text}
    </div>
  );
}
