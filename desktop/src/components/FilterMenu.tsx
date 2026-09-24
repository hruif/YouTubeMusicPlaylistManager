import { useEffect, useRef, useState } from "react";
import type { SongFilters } from "../lib/settings";

// One "Filter" button in place of separate toggles, so more filters can be added without widening
// the search bar. Shows how many filters are on.
const OPTIONS: { key: keyof SongFilters; label: string; hint: string }[] = [
  { key: "duplicates", label: "In more than one playlist", hint: "Songs that appear in two or more of the selected playlists" },
  { key: "unavailable", label: "Unavailable", hint: "Deleted, private, or otherwise unplayable videos (best-effort)" },
];

export function FilterMenu({ filters, onChange }: { filters: SongFilters; onChange: (next: SongFilters) => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const active = OPTIONS.filter((o) => filters[o.key]).length;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [open]);

  return (
    <div
      className="filter-menu"
      ref={rootRef}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation(); // close just this popover, not the modal/selection behind it
          setOpen(false);
        }
      }}
    >
      <button
        className={active ? "filter-on" : undefined}
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        Filter{active ? ` · ${active}` : ""}
      </button>
      {open && (
        <div className="filter-pop" role="group" aria-label="Song filters">
          {OPTIONS.map((o) => (
            <label key={o.key} className="filter-opt" title={o.hint}>
              <input
                type="checkbox"
                checked={filters[o.key]}
                onChange={(e) => onChange({ ...filters, [o.key]: e.currentTarget.checked })}
              />
              {o.label}
            </label>
          ))}
          {active > 0 && (
            <button
              className="small filter-clear"
              onClick={() => onChange(Object.fromEntries(OPTIONS.map((o) => [o.key, false])) as SongFilters)}
            >
              Clear filters
            </button>
          )}
        </div>
      )}
    </div>
  );
}
