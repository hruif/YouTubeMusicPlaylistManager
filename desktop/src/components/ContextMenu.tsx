import { useEffect, useRef } from "react";

export type MenuItem = { label: string; onClick: () => void };
export type MenuState = { x: number; y: number; items: MenuItem[] };

// Right-click menu. Keyboard: ↑/↓ move, Enter/Space choose, Esc closes (handled by App's Esc chain).
export function ContextMenu({ menu, onClose }: { menu: MenuState; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>(".ctx-item")?.focus();
  }, [menu]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = [...(ref.current?.querySelectorAll<HTMLElement>(".ctx-item") ?? [])];
    const at = items.indexOf(document.activeElement as HTMLElement);
    const next = e.key === "ArrowDown" ? (at + 1) % items.length : (at - 1 + items.length) % items.length;
    items[next]?.focus();
  }

  return (
    <>
      {/* Full-screen catcher: the first click anywhere just dismisses the menu and is consumed
          here, so it can't also close a modal, select a song, etc. The menu sits above it. */}
      <div
        className="menu-backdrop"
        onClick={onClose}
        onContextMenu={(e) => {
          e.preventDefault();
          onClose();
        }}
      />
      <div className="ctx-menu" role="menu" ref={ref} style={{ left: menu.x, top: menu.y }} onKeyDown={onKeyDown}>
        {menu.items.map((it) => (
          <button
            key={it.label}
            role="menuitem"
            className="ctx-item"
            onClick={() => {
              it.onClick();
              onClose();
            }}
          >
            {it.label}
          </button>
        ))}
      </div>
    </>
  );
}

// Position a menu at the pointer, clamped so it stays on-screen (flips up near the bottom edge).
export function menuAt(e: React.MouseEvent, items: MenuItem[]): MenuState {
  const estHeight = items.length * 30 + 8;
  const x = Math.min(e.clientX, window.innerWidth - 196);
  const y = Math.min(e.clientY, Math.max(8, window.innerHeight - estHeight - 8));
  return { x, y, items };
}
